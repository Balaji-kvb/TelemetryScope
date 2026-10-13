resource "aws_security_group" "cluster_sg" {
  name        = "telemetryscope-cluster-sg"
  description = "Security group for TelemetryScope EKS control plane"
  vpc_id      = aws_vpc.telemetryscope.id

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name = "telemetryscope-cluster-sg"
  }
}

resource "aws_eks_cluster" "main" {
  name     = var.cluster_name
  role_arn = aws_iam_role.cluster_role.arn
  version  = var.kubernetes_version

  vpc_config {
    subnet_ids              = concat(aws_subnet.public[*].id, aws_subnet.private[*].id)
    security_group_ids      = [aws_security_group.cluster_sg.id]
    endpoint_public_access  = true
    endpoint_private_access = true
    public_access_cidrs     = var.cluster_endpoint_public_access_cidrs
  }

  access_config {
    authentication_mode                         = "API_AND_CONFIG_MAP"
    bootstrap_cluster_creator_admin_permissions = true
  }

  depends_on = [
    aws_iam_role_policy_attachment.cluster_policy,
    aws_iam_role_policy_attachment.cluster_resource_controller,
  ]

  tags = {
    Name = var.cluster_name
  }
}

# Allow worker nodes to communicate with the EKS cluster API Server
resource "aws_security_group_rule" "cluster_ingress_node_https" {
  description              = "Allow worker nodes to communicate with the cluster API Server"
  type                     = "ingress"
  from_port                = 443
  to_port                  = 443
  protocol                 = "tcp"
  security_group_id        = aws_security_group.cluster_sg.id
  source_security_group_id = aws_security_group.node_sg.id
}

# Dedicated worker node security group with strict ingress controls
resource "aws_security_group" "node_sg" {
  name        = "telemetryscope-node-sg"
  description = "Security group for TelemetryScope EKS worker nodes"
  vpc_id      = aws_vpc.telemetryscope.id

  # Ingress: Allow intra-cluster node-to-node communication
  ingress {
    description = "Allow intra-cluster node-to-node traffic"
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    self        = true
  }

  # Ingress: Allow control plane to communicate with kubelet and pods
  ingress {
    description     = "Allow control plane to node kubelet"
    from_port       = 10250
    to_port         = 10250
    protocol        = "tcp"
    security_groups = [aws_security_group.cluster_sg.id]
  }

  # Ingress: Allow control plane to extension API webhooks
  ingress {
    description     = "Allow control plane to extension API webhooks"
    from_port       = 443
    to_port         = 443
    protocol        = "tcp"
    security_groups = [aws_security_group.cluster_sg.id]
  }

  # Ingress: Allow traffic from VPC (ALB / internal services) to NodePort range (30000-32767)
  ingress {
    description = "Allow internal VPC and ALB ingress to NodePort services"
    from_port   = 30000
    to_port     = 32767
    protocol    = "tcp"
    cidr_blocks = [var.vpc_cidr]
  }

  # Egress: Allow all outbound internet traffic via IGW
  egress {
    description = "Allow all outbound traffic"
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name = "telemetryscope-node-sg"
  }
}

# Launch Template for EKS Managed Nodes (configures gp3 root volume & security groups)
resource "aws_launch_template" "nodes" {
  name_prefix   = "telemetryscope-node-lt-"
  description   = "Launch template for TelemetryScope EKS managed node group"
  instance_type = var.node_instance_types[0]

  vpc_security_group_ids = [
    aws_security_group.node_sg.id,
    aws_eks_cluster.main.vpc_config[0].cluster_security_group_id
  ]

  block_device_mappings {
    device_name = "/dev/xvda"

    ebs {
      volume_size           = var.node_root_volume_size
      volume_type           = "gp3"
      delete_on_termination = true
      encrypted             = true
    }
  }

  tag_specifications {
    resource_type = "instance"
    tags = {
      Name                                        = "telemetryscope-worker-node"
      "kubernetes.io/cluster/${var.cluster_name}" = "owned"
    }
  }

  lifecycle {
    create_before_destroy = true
  }
}

# IAM OIDC Provider for EKS (required for IRSA / Load Balancer Controller / EBS CSI)
data "tls_certificate" "eks" {
  url = aws_eks_cluster.main.identity[0].oidc[0].issuer
}

resource "aws_iam_openid_connect_provider" "eks" {
  client_id_list  = ["sts.amazonaws.com"]
  thumbprint_list = [data.tls_certificate.eks.certificates[0].sha1_fingerprint]
  url             = aws_eks_cluster.main.identity[0].oidc[0].issuer

  tags = {
    Name = "${var.cluster_name}-oidc"
  }
}

resource "aws_eks_node_group" "main" {
  cluster_name    = aws_eks_cluster.main.name
  node_group_name = "telemetryscope-managed-nodes"
  node_role_arn   = aws_iam_role.node_role.arn
  subnet_ids      = aws_subnet.public[*].id

  launch_template {
    id      = aws_launch_template.nodes.id
    version = aws_launch_template.nodes.latest_version
  }

  scaling_config {
    desired_size = var.desired_nodes
    max_size     = var.max_nodes
    min_size     = var.min_nodes
  }

  update_config {
    max_unavailable = 1
  }

  depends_on = [
    aws_iam_role_policy_attachment.node_policy,
    aws_iam_role_policy_attachment.cni_policy,
    aws_iam_role_policy_attachment.registry_readonly,
  ]

  tags = {
    Name = "telemetryscope-managed-nodes"
  }
}

# EKS Addons
resource "aws_eks_addon" "vpc_cni" {
  cluster_name = aws_eks_cluster.main.name
  addon_name   = "vpc-cni"
}

resource "aws_eks_addon" "coredns" {
  cluster_name = aws_eks_cluster.main.name
  addon_name   = "coredns"
  depends_on   = [aws_eks_node_group.main]
}

resource "aws_eks_addon" "kube_proxy" {
  cluster_name = aws_eks_cluster.main.name
  addon_name   = "kube-proxy"
}

resource "aws_eks_addon" "ebs_csi" {
  cluster_name             = aws_eks_cluster.main.name
  addon_name               = "aws-ebs-csi-driver"
  service_account_role_arn = aws_iam_role.ebs_csi_role.arn
  depends_on               = [aws_eks_node_group.main]
}

# EKS Access Entry for GitHub Actions CD OIDC Role
resource "aws_eks_access_entry" "github_actions_cd" {
  cluster_name  = aws_eks_cluster.main.name
  principal_arn = aws_iam_role.github_actions_cd.arn
  type          = "STANDARD"
}

# Namespace-scoped admin permissions restricted to telemetryscope application namespace
resource "aws_eks_access_policy_association" "github_actions_cd_namespace" {
  cluster_name  = aws_eks_cluster.main.name
  policy_arn    = "arn:aws:eks::aws:cluster-access-policy/AmazonEKSAdminPolicy"
  principal_arn = aws_eks_access_entry.github_actions_cd.principal_arn

  access_scope {
    type       = "namespace"
    namespaces = ["telemetryscope"]
  }

  depends_on = [aws_eks_access_entry.github_actions_cd]
}

# Cluster-scoped view permissions (read-only for cluster inspection and node/namespace discovery)
resource "aws_eks_access_policy_association" "github_actions_cd_view" {
  cluster_name  = aws_eks_cluster.main.name
  policy_arn    = "arn:aws:eks::aws:cluster-access-policy/AmazonEKSViewPolicy"
  principal_arn = aws_eks_access_entry.github_actions_cd.principal_arn

  access_scope {
    type = "cluster"
  }

  depends_on = [aws_eks_access_entry.github_actions_cd]
}


