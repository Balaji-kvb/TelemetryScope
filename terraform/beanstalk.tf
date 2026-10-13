# Elastic Beanstalk Application for Staging Tier Proof
resource "aws_elastic_beanstalk_application" "staging" {
  name        = "telemetryscope-staging"
  description = "TelemetryScope Staging Application environment"

  tags = {
    Name = "telemetryscope-staging"
  }
}

# Elastic Beanstalk Service Role
resource "aws_iam_role" "beanstalk_service" {
  count = var.enable_beanstalk_environment ? 1 : 0
  name  = "telemetryscope-beanstalk-service-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Principal = {
          Service = "elasticbeanstalk.amazonaws.com"
        }
        Action = "sts:AssumeRole"
      }
    ]
  })
}

resource "aws_iam_role_policy_attachment" "beanstalk_service_health" {
  count      = var.enable_beanstalk_environment ? 1 : 0
  role       = aws_iam_role.beanstalk_service[0].name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSElasticBeanstalkEnhancedHealth"
}

# Elastic Beanstalk EC2 Instance Profile Role
resource "aws_iam_role" "beanstalk_ec2" {
  count = var.enable_beanstalk_environment ? 1 : 0
  name  = "telemetryscope-beanstalk-ec2-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Principal = {
          Service = "ec2.amazonaws.com"
        }
        Action = "sts:AssumeRole"
      }
    ]
  })
}

resource "aws_iam_role_policy_attachment" "beanstalk_ec2_web" {
  count      = var.enable_beanstalk_environment ? 1 : 0
  role       = aws_iam_role.beanstalk_ec2[0].name
  policy_arn = "arn:aws:iam::aws:policy/AWSElasticBeanstalkWebTier"
}

resource "aws_iam_instance_profile" "beanstalk_ec2" {
  count = var.enable_beanstalk_environment ? 1 : 0
  name  = "telemetryscope-beanstalk-ec2-profile"
  role  = aws_iam_role.beanstalk_ec2[0].name
}

# Temporary Single-Instance Elastic Beanstalk Environment (No ALB, minimal cost)
resource "aws_elastic_beanstalk_environment" "staging" {
  count               = var.enable_beanstalk_environment ? 1 : 0
  name                = "telemetryscope-staging-env"
  application         = aws_elastic_beanstalk_application.staging.name
  solution_stack_name = "64bit Amazon Linux 2023 v4.13.10 running Python 3.11"
  tier                = "WebServer"

  setting {
    namespace = "aws:elasticbeanstalk:environment"
    name      = "EnvironmentType"
    value     = "SingleInstance"
  }

  setting {
    namespace = "aws:autoscaling:launchconfiguration"
    name      = "IamInstanceProfile"
    value     = aws_iam_instance_profile.beanstalk_ec2[0].name
  }

  setting {
    namespace = "aws:autoscaling:launchconfiguration"
    name      = "InstanceType"
    value     = "t3.micro"
  }

  setting {
    namespace = "aws:elasticbeanstalk:environment"
    name      = "ServiceRole"
    value     = aws_iam_role.beanstalk_service[0].name
  }

  setting {
    namespace = "aws:elasticbeanstalk:application:environment"
    name      = "TELEMETRYSCOPE_ENV"
    value     = "staging"
  }

  tags = {
    Name        = "telemetryscope-staging-env"
    Environment = "staging"
  }
}
