locals {
  provision_script_url = "https://gitlab.com/ViteMaDose/vitemadose/-/raw/main/gitlab-runner/deploy-dev-runner.sh"
}


data "openstack_images_image_v2" "debian_9" {
  provider    = openstack.ovh
  name        = "Debian 9"
  most_recent = true
}

resource "openstack_compute_instance_v2" "runner" {
  provider        = openstack.ovh
  count           = var.nb_instances
  flavor_name     = var.flavor
  image_id        = data.openstack_images_image_v2.debian_9.id
  name            = "${var.name}-${count.index}-${var.ovh_region}"
  security_groups = ["default"]
  key_pair        = openstack_compute_keypair_v2.runner_keypair.name

  lifecycle {
    ignore_changes = [image_id, user_data]
    create_before_destroy = false
  }
}

resource null_resource "register_runner" {
  count = var.nb_instances
  triggers = {
    private_key = openstack_compute_keypair_v2.runner_keypair.private_key
    host = openstack_compute_instance_v2.runner[count.index].access_ip_v4
    user = "debian"
  }
  connection {
    user = self.triggers.user
    private_key = self.triggers.private_key
    host = self.triggers.host
    timeout = "45s"
  }

  provisioner "file" {
    source = "./provision.sh"
    destination = "/tmp/provision-${random_string.provision_name.id}.sh"
  }

  provisioner "remote-exec" {
    inline = [
      "export GITLAB_RUNNER_TOKEN=${var.gitlab_runner_token}",
      "export RUNNER_LOCATION='OVH ${var.ovh_region} (num ${count.index})'",
      "export TAG_LIST='ovh,ovh-${var.ovh_region},${formatdate("DD MMM YYYY hh:mm ZZZ", timestamp())}'",
      "export GITLAB_RUN_UNTAGGED=yes",
      "sudo -E bash /tmp/provision-${random_string.provision_name.id}.sh"
    ]
  }

  provisioner "remote-exec" {
    when = destroy
    on_failure = continue
    inline = [
      "sudo gitlab-runner unregister --all-runners"
    ]
  }
}

resource random_string provision_name {
  length = 6
  special = false
}

resource "openstack_compute_keypair_v2" "runner_keypair" {
  provider        = openstack.ovh
  name            = "runners-${random_string.key_pair_name.result}"
}

resource "random_string" "key_pair_name" {
  length           = 20
  special          = false
}
