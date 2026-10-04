// type-10042026-Maurice: AWS private multi-AZ foundation;application resources remain Argo-owned.
provider "aws" {
  region = var.region
  default_tags {
    tags = merge(var.tags, {
      Environment = var.environment, ManagedBy = "terraform"
    })
  }
}
data "tls_certificate" "eks" {
  url = aws_eks_cluster.this.identity[0].oidc[0].issuer
}
data "aws_availability_zones" "available" {
  state = "available"
}
resource "aws_kms_key" "platform" {
  description             = "${var.name} platform encryption"
  enable_key_rotation     = true
  deletion_window_in_days = var.environment == "production" ? 30 : 7
}
resource "aws_vpc" "this" {
  cidr_block           = var.vpc_cidr
  enable_dns_support   = true
  enable_dns_hostnames = true
  tags = {
    Name = var.name
  }
}
resource "aws_internet_gateway" "this" {
  vpc_id = aws_vpc.this.id
}
resource "aws_subnet" "private" {
  count             = length(var.private_subnet_cidrs)
  vpc_id            = aws_vpc.this.id
  cidr_block        = var.private_subnet_cidrs[count.index]
  availability_zone = var.availability_zones[count.index]
  tags = {
    Name                              = "${var.name}-private-${count.index}"
    "kubernetes.io/role/internal-elb" = "1"
  }
}
resource "aws_subnet" "public" {
  count                   = length(var.public_subnet_cidrs)
  vpc_id                  = aws_vpc.this.id
  cidr_block              = var.public_subnet_cidrs[count.index]
  availability_zone       = var.availability_zones[count.index]
  map_public_ip_on_launch = false
  tags = {
    Name                     = "${var.name}-public-${count.index}"
    "kubernetes.io/role/elb" = "1"
  }
}
resource "aws_subnet" "data" {
  count             = length(var.database_subnet_cidrs)
  vpc_id            = aws_vpc.this.id
  cidr_block        = var.database_subnet_cidrs[count.index]
  availability_zone = var.availability_zones[count.index]
  tags = {
    Name = "${var.name}-data-${count.index}"
  }
}
resource "aws_eip" "nat" {
  count  = length(var.public_subnet_cidrs)
  domain = "vpc"
}
resource "aws_nat_gateway" "this" {
  count         = length(var.public_subnet_cidrs)
  allocation_id = aws_eip.nat[count.index].id
  subnet_id     = aws_subnet.public[count.index].id
  depends_on    = [aws_internet_gateway.this]
}
resource "aws_eks_cluster" "this" {
  name     = var.name
  role_arn = aws_iam_role.eks.arn
  version  = var.kubernetes_version
  vpc_config {
    subnet_ids              = aws_subnet.private[*].id
    endpoint_private_access = true
    endpoint_public_access  = false
    public_access_cidrs     = var.admin_cidrs
    security_group_ids      = [aws_security_group.cluster.id]
  }
  encryption_config {
    provider {
      key_arn = aws_kms_key.platform.arn
    }
    resources = ["secrets"]
  }
  enabled_cluster_log_types = ["api", "audit", "authenticator", "controllerManager", "scheduler"]
}
resource "aws_security_group" "cluster" {
  name   = "${var.name}-cluster"
  vpc_id = aws_vpc.this.id
  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = [var.vpc_cidr]
  }
}
resource "aws_iam_role" "eks" {
  name = "${var.name}-eks"
  assume_role_policy = jsonencode({ Version = "2012-10-17", Statement = [{ Effect = "Allow", Principal = {
    Service   = "eks.amazonaws.com"
    }, Action = "sts:AssumeRole"
    }]
  })
}
resource "aws_iam_role_policy_attachment" "eks" {
  role       = aws_iam_role.eks.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonEKSClusterPolicy"
}
resource "aws_eks_node_group" "managed" {
  cluster_name    = aws_eks_cluster.this.name
  node_group_name = "${var.name}-managed"
  node_role_arn   = aws_iam_role.nodes.arn
  subnet_ids      = aws_subnet.private[*].id
  instance_types  = var.node_instance_types
  capacity_type   = "ON_DEMAND"
  scaling_config {
    min_size     = var.node_min_size
    desired_size = var.node_min_size
    max_size     = var.node_max_size
  }
  update_config {
    max_unavailable = 1
  }
  depends_on = [aws_iam_role_policy_attachment.nodes]
}
resource "aws_iam_role" "nodes" {
  name = "${var.name}-nodes"
  assume_role_policy = jsonencode({ Version = "2012-10-17", Statement = [{ Effect = "Allow", Principal = {
    Service   = "ec2.amazonaws.com"
    }, Action = "sts:AssumeRole"
    }]
  })
}
resource "aws_iam_role_policy_attachment" "nodes" {
  for_each   = toset(["AmazonEKSWorkerNodePolicy", "AmazonEC2ContainerRegistryReadOnly", "AmazonEKS_CNI_Policy"])
  role       = aws_iam_role.nodes.name
  policy_arn = "arn:aws:iam::aws:policy/${each.key}"
}
resource "aws_ecr_repository" "app" {
  name                 = var.name
  image_tag_mutability = "IMMUTABLE"
  image_scanning_configuration {
    scan_on_push = true
  }
  encryption_configuration {
    encryption_type = "KMS"
    kms_key         = aws_kms_key.platform.arn
  }
}
resource "aws_db_subnet_group" "this" {
  name       = var.name
  subnet_ids = aws_subnet.data[*].id
}
resource "aws_db_instance" "postgres" {
  identifier              = "${var.name}-postgres"
  engine                  = "postgres"
  engine_version          = "16"
  instance_class          = var.environment == "production" ? "db.m6g.large" : "db.t4g.micro"
  allocated_storage       = 100
  storage_encrypted       = true
  kms_key_id              = aws_kms_key.platform.arn
  multi_az                = true
  db_subnet_group_name    = aws_db_subnet_group.this.name
  publicly_accessible     = false
  backup_retention_period = var.environment == "production" ? 35 : 7
  backup_window           = "03:00-03:30"
  maintenance_window      = "sun:04:00-sun:04:30"
  deletion_protection     = var.environment == "production"
  skip_final_snapshot     = var.environment != "production"
  apply_immediately       = false
}
resource "aws_elasticache_subnet_group" "this" {
  name       = var.name
  subnet_ids = aws_subnet.data[*].id
}
resource "aws_elasticache_replication_group" "redis" {
  replication_group_id       = var.name
  description                = "${var.name} private Redis"
  node_type                  = var.environment == "production" ? "cache.t4g.medium" : "cache.t4g.micro"
  num_cache_clusters         = 2
  multi_az_enabled           = true
  automatic_failover_enabled = true
  at_rest_encryption_enabled = true
  transit_encryption_enabled = true
  kms_key_id                 = aws_kms_key.platform.arn
  subnet_group_name          = aws_elasticache_subnet_group.this.name
}
resource "aws_efs_file_system" "shared" {
  encrypted  = true
  kms_key_id = aws_kms_key.platform.arn
  lifecycle_policy {
    transition_to_ia = "AFTER_30_DAYS"
  }
  protection {
    replication_overwrite = "DISABLED"
  }
}
resource "aws_secretsmanager_secret" "platform" {
  name                    = "${var.name}/platform"
  kms_key_id              = aws_kms_key.platform.arn
  recovery_window_in_days = var.environment == "production" ? 30 : 7
}
resource "aws_iam_openid_connect_provider" "eks" {
  url             = aws_eks_cluster.this.identity[0].oidc[0].issuer
  client_id_list  = ["sts.amazonaws.com"]
  thumbprint_list = [data.tls_certificate.eks.certificates[0].sha1_fingerprint]
}
resource "helm_release" "argo" {
  count            = var.bootstrap_argo ? 1 : 0
  name             = "argocd"
  namespace        = "argocd"
  create_namespace = true
  repository       = "https://argoproj.github.io/argo-helm"
  chart            = "argo-cd"
  version          = var.argo_chart_version
  values = [yamlencode({ server = {
    service = {
      type = "ClusterIP"
    }
    }
  })]
  depends_on = [aws_eks_node_group.managed]
}
