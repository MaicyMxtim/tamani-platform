# Tamani platform node: a single EC2 instance running k3s, fronted by an
# Elastic IP, with DNS under platform.waypear.com. Applied only after cost
# is confirmed. State starts local; the S3 backend is bootstrapped later.

data "aws_ami" "ubuntu" {
  most_recent = true
  owners      = ["099720109477"] # Canonical

  filter {
    name   = "name"
    values = ["ubuntu/images/hvm-ssd-gp3/ubuntu-noble-24.04-amd64-server-*"]
  }
}

resource "aws_security_group" "node" {
  name        = "tamani-node"
  description = "k3s single node: ssh, http, https, k8s api"

  dynamic "ingress" {
    for_each = { ssh = 22, http = 80, https = 443, k8s_api = 6443 }
    content {
      description = ingress.key
      from_port   = ingress.value
      to_port     = ingress.value
      protocol    = "tcp"
      cidr_blocks = ingress.key == "ssh" || ingress.key == "k8s_api" ? [var.admin_cidr] : ["0.0.0.0/0"]
    }
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

resource "aws_key_pair" "admin" {
  key_name   = "tamani-admin"
  public_key = var.ssh_public_key
}

resource "aws_instance" "node" {
  ami                    = data.aws_ami.ubuntu.id
  instance_type          = var.instance_type
  key_name               = aws_key_pair.admin.key_name
  vpc_security_group_ids = [aws_security_group.node.id]
  user_data              = file("${path.module}/user_data.sh")

  root_block_device {
    volume_size = 40
    volume_type = "gp3"
  }

  tags = { Name = "tamani-platform-node" }
}

resource "aws_eip" "node" {
  instance = aws_instance.node.id
}

resource "aws_route53_zone" "waypear" {
  name = var.domain
}

resource "aws_route53_record" "platform" {
  zone_id = aws_route53_zone.waypear.zone_id
  name    = "platform.${var.domain}"
  type    = "A"
  ttl     = 300
  records = [aws_eip.node.public_ip]
}

resource "aws_route53_record" "wildcard" {
  zone_id = aws_route53_zone.waypear.zone_id
  name    = "*.platform.${var.domain}"
  type    = "A"
  ttl     = 300
  records = [aws_eip.node.public_ip]
}

resource "aws_s3_bucket" "backups" {
  bucket_prefix = "tamani-backups-"
}

resource "aws_s3_bucket_lifecycle_configuration" "backups" {
  bucket = aws_s3_bucket.backups.id
  rule {
    id     = "expire-old-backups"
    status = "Enabled"
    filter {}
    expiration { days = 30 }
  }
}
