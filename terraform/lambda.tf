# Packaging Lambda Alert Handler
data "archive_file" "alert_handler" {
  type        = "zip"
  source_file = "${path.module}/../lambda/alert-handler/index.py"
  output_path = "${path.module}/alert_handler.zip"
}

# IAM Role for Lambda
resource "aws_iam_role" "lambda_role" {
  name = "telemetryscope-lambda-alert-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "lambda.amazonaws.com"
        }
      }
    ]
  })

  tags = {
    Name = "telemetryscope-lambda-alert-role"
  }
}

resource "aws_iam_role_policy_attachment" "lambda_basic_execution" {
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
  role       = aws_iam_role.lambda_role.name
}

# Lambda Alert Handler Function
resource "aws_lambda_function" "alert_handler" {
  function_name    = "telemetryscope-alert-handler"
  role             = aws_iam_role.lambda_role.arn
  handler          = "index.lambda_handler"
  runtime          = "python3.11"
  filename         = data.archive_file.alert_handler.output_path
  source_code_hash = data.archive_file.alert_handler.output_base64sha256

  environment {
    variables = {
      ENVIRONMENT = var.environment
    }
  }

  tags = {
    Name = "telemetryscope-alert-handler"
  }
}

# CloudWatch Log Group for Lambda
resource "aws_cloudwatch_log_group" "lambda_logs" {
  name              = "/aws/lambda/${aws_lambda_function.alert_handler.function_name}"
  retention_in_days = 7

  tags = {
    Name = "telemetryscope-lambda-logs"
  }
}
