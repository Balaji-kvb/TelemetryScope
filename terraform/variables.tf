variable "aws_region" {
  description = "AWS region for TelemetryScope infrastructure"
  type        = string
  default     = "ap-south-1"
}

variable "environment" {
  description = "Deployment environment name"
  type        = string
  default     = "staging"
}

variable "cluster_name" {
  description = "Amazon EKS cluster name"
  type        = string
  default     = "telemetryscope-cluster"
}

variable "vpc_cidr" {
  description = "CIDR block for the TelemetryScope VPC"
  type        = string
  default     = "10.0.0.0/16"
}

variable "availability_zones" {
  description = "Availability zones in the region"
  type        = list(string)
  default     = ["ap-south-1a", "ap-south-1b"]
}

variable "public_subnet_cidrs" {
  description = "CIDR blocks for public subnets"
  type        = list(string)
  default     = ["10.0.1.0/24", "10.0.2.0/24"]
}

variable "private_subnet_cidrs" {
  description = "CIDR blocks for private subnets"
  type        = list(string)
  default     = ["10.0.11.0/24", "10.0.12.0/24"]
}

variable "node_instance_types" {
  description = "EC2 instance types for EKS managed node group"
  type        = list(string)
  default     = ["c7i-flex.large"]
}

variable "desired_nodes" {
  description = "Desired number of worker nodes"
  type        = number
  default     = 2
}

variable "min_nodes" {
  description = "Minimum number of worker nodes"
  type        = number
  default     = 1
}

variable "max_nodes" {
  description = "Maximum number of worker nodes"
  type        = number
  default     = 3
}

variable "kubernetes_version" {
  description = "Kubernetes version for the EKS cluster (standard support)"
  type        = string
  default     = "1.36"
}

variable "cluster_endpoint_public_access_cidrs" {
  description = "List of CIDR blocks permitted to access the public EKS API endpoint"
  type        = list(string)
  default     = ["0.0.0.0/0"]
}

variable "node_root_volume_size" {
  description = "EBS root volume size in GB for each worker node"
  type        = number
  default     = 20
}

variable "enable_nat_gateway" {
  description = "Whether to provision a NAT Gateway for private subnets (costs ~$32.40/mo in ap-south-1)"
  type        = bool
  default     = false
}

variable "enable_beanstalk_environment" {
  description = "Whether to provision the temporary Elastic Beanstalk compute environment (gated by cost review)"
  type        = bool
  default     = false
}

