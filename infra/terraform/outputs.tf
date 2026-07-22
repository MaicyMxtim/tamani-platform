output "node_ip" {
  value = aws_eip.node.public_ip
}

output "platform_fqdn" {
  value = aws_route53_record.platform.fqdn
}

output "nameservers" {
  description = "Set these at the waypear.com registrar to delegate DNS to Route53"
  value       = aws_route53_zone.waypear.name_servers
}

output "backup_bucket" {
  value = aws_s3_bucket.backups.bucket
}
