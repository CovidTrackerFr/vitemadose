locals {
  provision_script_url = "https://gitlab.com/ViteMaDose/vitemadose/-/raw/main/gitlab-runner/deploy-dev-runner.sh"
}


data "openstack_images_image_v2" "debian_9" {
  provider    = openstack.ovh
  name        = "Debian 10"
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
    create_before_destroy = false
  }
}

resource null_resource "register_runner" {
  count = var.nb_instances
  triggers = {
    private_key = openstack_compute_keypair_v2.runner_keypair.private_key
    host = openstack_compute_instance_v2.runner[count.index].access_ip_v4
    user = "debian"
    gitlab_runner_token = var.gitlab_runner_token
    ovh_region = var.ovh_region
    datadog_api_key = var.datadog_api_key
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
      "export GITLAB_RUNNER_TOKEN=${self.triggers.gitlab_runner_token}",
      "export RUNNER_LOCATION='OVH ${self.triggers.ovh_region} (num ${count.index})'",
      "export TAG_LIST='ovh,ovh-${self.triggers.ovh_region},${formatdate("DD MMM YYYY hh:mm ZZZ", timestamp())}'",
      "export DD_API_KEY=${self.triggers.datadog_api_key}",
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
