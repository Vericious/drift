# Sample Terraform configuration for testing

# Variables
variable "region" {
  type        = string
  default     = "us-west-2"
  description = "AWS region to deploy resources"
}

variable "environment" {
  type        = string
  default     = "dev"
  description = "Environment name"
}

variable "instance_type" {
  type        = string
  default     = "t3.micro"
  description = "EC2 instance type"
}

variable "tags" {
  type        = map(string)
  default     = {}
  description = "Resource tags"
}

# S3 Bucket Resource
resource "aws_s3_bucket" "app_bucket" {
  bucket = "my-app-${var.environment}-bucket"
  acl    = "private"

  tags = merge(var.tags, {
    Environment = var.environment
    ManagedBy   = "Terraform"
  })
}

resource "aws_s3_bucket_versioning" "app_bucket_versioning" {
  bucket = aws_s3_bucket.app_bucket.id

  versioning_configuration {
    status = "Enabled"
  }
}

# EC2 Instance Resource
resource "aws_instance" "web_server" {
  ami           = "ami-0c55b159cbfafe1f0"
  instance_type = var.instance_type
  subnet_id     = aws_subnet.main.id

  tags = {
    Name        = "web-server-${var.environment}"
    Environment = var.environment
  }
}

# VPC Subnet Resource
resource "aws_vpc" "main" {
  cidr_block = "10.0.0.0/16"

  tags = {
    Name = "main-vpc-${var.environment}"
  }
}

resource "aws_subnet" "main" {
  vpc_id                  = aws_vpc.main.id
  cidr_block              = "10.0.1.0/24"
  availability_zone       = "${var.region}a"

  tags = {
    Name = "main-subnet-${var.environment}"
  }
}

# Data source
data "aws_ami" "ubuntu" {
  most_recent = true
  owners      = ["099720109477"]

  filter {
    name   = "name"
    values = ["ubuntu/images/hvm-ssd/ubuntu-jammy-22.04-amd64-server-*"]
  }
}

# Outputs
output "bucket_name" {
  description = "S3 bucket name"
  value       = aws_s3_bucket.app_bucket.id
}

output "instance_ip" {
  description = "Web server IP address"
  value       = aws_instance.web_server.private_ip
}

output "vpc_id" {
  description = "VPC ID"
  value       = aws_vpc.main.id
}
