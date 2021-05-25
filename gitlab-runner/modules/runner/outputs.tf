output "public_ips" {
  value = openstack_compute_instance_v2.runner[*].access_ip_v4
}

output "instance_ids" {
  value = openstack_compute_instance_v2.runner[*].id
}
