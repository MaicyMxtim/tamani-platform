variable "region" {
  type    = string
  default = "eu-west-2" # London, closest to Brighton traffic
}

variable "domain" {
  type    = string
  default = "waypear.com"
}

variable "instance_type" {
  type        = string
  default     = "t3.small"
  description = "2 GB RAM runs the core stack tightly; t3.medium (4 GB) is comfortable once observability and Argo CD land. Cost roughly doubles."
}

variable "admin_cidr" {
  type        = string
  description = "CIDR allowed to reach ssh and the k8s api, e.g. your-ip/32"
}

variable "ssh_public_key" {
  type        = string
  description = "Public key for the admin keypair"
}
