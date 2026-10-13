output "vpc_id" {
  description = "ID of the TelemetryScope VPC"
  value       = aws_vpc.telemetryscope.id
}

output "eks_cluster_name" {
  description = "Name of the EKS cluster"
  value       = aws_eks_cluster.main.name
}

output "eks_cluster_endpoint" {
  description = "Endpoint for EKS control plane"
  value       = aws_eks_cluster.main.endpoint
}

output "eks_cluster_arn" {
  description = "ARN of the EKS cluster"
  value       = aws_eks_cluster.main.arn
}

output "eks_cluster_version" {
  description = "Kubernetes version of the EKS cluster"
  value       = aws_eks_cluster.main.version
}

output "oidc_provider_arn" {
  description = "ARN of the EKS OIDC identity provider"
  value       = aws_iam_openid_connect_provider.eks.arn
}

output "ebs_csi_role_arn" {
  description = "ARN of the IAM role for EBS CSI Driver"
  value       = aws_iam_role.ebs_csi_role.arn
}

output "alb_controller_role_arn" {
  description = "ARN of the IAM role for AWS Load Balancer Controller"
  value       = aws_iam_role.alb_controller_role.arn
}

output "ecr_repository_urls" {
  description = "Map of ECR repository URLs"
  value       = { for k, v in aws_ecr_repository.services : k => v.repository_url }
}

output "lambda_function_name" {
  description = "Name of the Lambda alert handler function"
  value       = aws_lambda_function.alert_handler.function_name
}

output "lambda_function_arn" {
  description = "ARN of the Lambda alert handler function"
  value       = aws_lambda_function.alert_handler.arn
}

output "elastic_beanstalk_application_name" {
  description = "Name of the Elastic Beanstalk application"
  value       = aws_elastic_beanstalk_application.staging.name
}

output "github_actions_cd_role_arn" {
  description = "ARN of the IAM role for GitHub Actions OIDC continuous deployment"
  value       = aws_iam_role.github_actions_cd.arn
}

output "elastic_beanstalk_environment_endpoint" {
  description = "Endpoint URL of the Elastic Beanstalk staging environment"
  value       = var.enable_beanstalk_environment ? try(aws_elastic_beanstalk_environment.staging[0].cname, null) : null
}

