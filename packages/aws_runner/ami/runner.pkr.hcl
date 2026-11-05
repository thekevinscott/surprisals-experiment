packer {
  required_version = "= 1.16.2"
  required_plugins {
    amazon = {
      version = "= 1.8.4"
      source  = "github.com/hashicorp/amazon"
    }
  }
}

variable "region" {
  type = string
}

variable "ubuntu_ami" {
  type        = string
  description = "Pinned Canonical Ubuntu 24.04 x86_64 EBS AMI ID in region."
}

source "amazon-ebs" "runner" {
  region        = var.region
  instance_type = "m6i.large"
  ami_name      = "surprisals-runner-${formatdate("YYYYMMDDhhmmss", timestamp())}"
  ssh_username  = "ubuntu"

  source_ami_filter {
    filters = {
      image-id            = var.ubuntu_ami
      name                = "ubuntu/images/hvm-ssd-gp3/ubuntu-noble-24.04-amd64-server-*"
      architecture        = "x86_64"
      root-device-type    = "ebs"
      virtualization-type = "hvm"
    }
    owners = ["099720109477"]
  }

  associate_public_ip_address               = true
  temporary_security_group_source_public_ip = true
  ssh_clear_authorized_keys                 = true
  ssh_disable_agent_forwarding              = true
  imds_support                              = "v2.0"

  metadata_options {
    http_tokens = "required"
  }

  launch_block_device_mappings {
    device_name           = "/dev/sda1"
    volume_type           = "gp3"
    volume_size           = 40
    delete_on_termination = true
  }

  tags = {
    Name = "surprisals-runner"
  }
}

build {
  sources = ["source.amazon-ebs.runner"]

  provisioner "file" {
    source      = "${path.root}/../../../surprisals_experiment/src/surprisals_experiment/docker/Dockerfile.t"
    destination = "/tmp/Dockerfile.t"
  }

  provisioner "shell" {
    script          = "${path.root}/provision.sh"
    execute_command = "sudo bash '{{ .Path }}'"
  }

  provisioner "file" {
    direction   = "download"
    source      = "/usr/local/share/aws-runner/images.json"
    destination = "${path.root}/artifacts/images.json"
  }

  provisioner "file" {
    direction   = "download"
    source      = "/usr/local/share/aws-runner/versions.txt"
    destination = "${path.root}/artifacts/versions.txt"
  }

  provisioner "shell" {
    inline = [
      "sudo cloud-init clean --logs --machine-id",
      "sudo rm -f /etc/ssh/ssh_host_*",
    ]
  }

  post-processor "manifest" {
    output = "${path.root}/artifacts/manifest.json"
    custom_data = {
      ubuntu_ami    = var.ubuntu_ami
      botbox_commit = "4fed2b153f15e216d9b07109355b83a6d7bdf819"
      images        = "images.json"
      versions      = "versions.txt"
    }
  }
}
