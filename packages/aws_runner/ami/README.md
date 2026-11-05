# AWS runner AMI

Packer 1.16.2 builds an x86_64 Ubuntu 24.04 AMI with Docker, Buildx, rsync, uv 0.13.7, Botbox Pi and proxy images, the digest-pinned Envoy credential proxy, and the experiment's Python overlay. Botbox source is pinned to the experiment's current commit `4fed2b153f15e216d9b07109355b83a6d7bdf819` and archive SHA256. Only `Dockerfile.t` is uploaded; no checkout, `.env`, AWS profile, agent home, or credentials are copied into the image. The builder uses no instance role.

From this directory, with Packer installed and AWS access configured **on the build host**, choose a specific Canonical Ubuntu 24.04 amd64 AMI in the intended region and build:

```sh
mkdir -p artifacts && packer init . && packer build -var 'region=us-east-1' -var "ubuntu_ami=$UBUNTU_AMI_ID" .
```

The template verifies the source AMI's Canonical owner, Ubuntu release, architecture, and EBS type. It does not select a moving `most_recent` image. The temporary build instance uses an On-Demand `m6i.large`, a 40-GiB gp3 disk, and SSH restricted to the builder's public IP; this assumes a default VPC with outbound internet. Its temporary disk is deleted on termination. The runner's retained run volume is configured separately by `aws_runner` (#150).

After a successful build, retain these three files together as the image release record:

- `artifacts/manifest.json`: Packer's `region:ami-ID` artifact, source Ubuntu AMI, and Botbox revision. Pin that resulting AMI ID in the runner's launch configuration; never resolve a latest-by-name AMI at run time.
- `artifacts/images.json`: loaded image tags, immutable SHA256 image IDs, registry digests where available, and architecture. Locally built Pi/proxy/overlay images have image IDs rather than registry RepoDigests because they are not pushed to a registry.
- `artifacts/versions.txt`: uv, installed Docker/Buildx/rsync versions, and the experiment Dockerfile hash. These inventories also live at `/usr/local/share/aws-runner/` inside the AMI.

Botbox tags its experiment overlay using the absolute Dockerfile path. `botbox-experiment:ami` warms its layers; the first build from a different rsynced path will create the path-specific tag using Docker's cache. Preserve `/var/lib/docker`, including the build cache. No model request is made while baking. Pi, Python, and Envoy offline version checks run during provisioning.

The AMI pins the resulting filesystem and image IDs. Rebuilding can resolve newer Ubuntu packages or the upstream Pi Dockerfile's tagged Node base; compare the inventories before adopting a replacement AMI. Rebuild when the experiment's Botbox revision or Dockerfile changes.

Credential-free checks (the all-zero AMI is a validation placeholder, never a build input):

```sh
packer init .
packer fmt -check .
AWS_CONFIG_FILE=/dev/null AWS_SHARED_CREDENTIALS_FILE=/dev/null AWS_EC2_METADATA_DISABLED=true packer validate -var 'region=us-east-1' -var 'ubuntu_ami=ami-00000000000000000' .
bash -n provision.sh
uvx --from shellcheck-py==0.11.0.1 shellcheck provision.sh
```

No AMI has been built or assigned an ID yet. Real AWS still needs: a successful bake from the selected source AMI; a fresh launch with the intended key and no instance role; Docker access as `ubuntu` and image/cache checks; confirmation that cloud-init installs only the new launch key; and one rsynced experiment smoke run using the pinned result AMI. Build/launch/volume lifecycle belongs to #150's runner, not this template.

References: [Packer amazon-ebs](https://developer.hashicorp.com/packer/integrations/hashicorp/amazon/latest/components/builder/ebs), [manifest output](https://developer.hashicorp.com/packer/docs/post-processors/manifest).
