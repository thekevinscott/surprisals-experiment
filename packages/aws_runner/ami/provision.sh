#!/usr/bin/env bash
set -euo pipefail

cloud-init status --wait
export DEBIAN_FRONTEND=noninteractive
apt-get update
apt-get install -y --no-install-recommends ca-certificates curl docker.io docker-buildx jq rsync
systemctl enable --now docker
usermod -aG docker ubuntu

curl -fsSL https://github.com/astral-sh/uv/releases/download/0.13.7/uv-x86_64-unknown-linux-gnu.tar.gz -o /tmp/uv.tar.gz
echo 'c5221ff41b7892bfc223543883600125f6a47fe845093e0f5bdff4f359196d83  /tmp/uv.tar.gz' | sha256sum -c -
tar -xzf /tmp/uv.tar.gz -C /tmp
install -m 0755 /tmp/uv-x86_64-unknown-linux-gnu/uv /tmp/uv-x86_64-unknown-linux-gnu/uvx /usr/local/bin/

curl -fsSL https://github.com/thekevinscott/botbox/archive/4fed2b153f15e216d9b07109355b83a6d7bdf819.tar.gz -o /tmp/botbox.tar.gz
echo '18d3136f054a867b58d757086fadbef451183e6a04e2a2de66a1618ea4d395d3  /tmp/botbox.tar.gz' | sha256sum -c -
tar -xzf /tmp/botbox.tar.gz -C /tmp
botbox_source=/tmp/botbox-4fed2b153f15e216d9b07109355b83a6d7bdf819/packages/python/src/botbox

docker buildx build --load --platform linux/amd64 --build-context "botbox=$botbox_source/relay" -t botbox-pi:latest "$botbox_source/agents/pi"
docker buildx build --load --platform linux/amd64 -t botbox-proxy:latest "$botbox_source/proxy"
docker pull --platform linux/amd64 envoyproxy/envoy:v1.36.2@sha256:4972515dd9a069b44beb43cebba7851596e72a8c61cd7a7c33d8f48efc5280ba
mkdir /tmp/t-image
cp /tmp/Dockerfile.t /tmp/t-image/Dockerfile
docker buildx build --load --platform linux/amd64 -t botbox-experiment:ami /tmp/t-image

install -d /usr/local/share/aws-runner
docker image inspect botbox-pi:latest botbox-proxy:latest botbox-experiment:ami envoyproxy/envoy:v1.36.2@sha256:4972515dd9a069b44beb43cebba7851596e72a8c61cd7a7c33d8f48efc5280ba | jq '[.[] | {tags: .RepoTags, id: .Id, repo_digests: .RepoDigests, architecture: .Architecture}]' > /usr/local/share/aws-runner/images.json
{
  uv --version
  docker --version
  dpkg-query -W docker.io docker-buildx rsync
  sha256sum /tmp/Dockerfile.t
} > /usr/local/share/aws-runner/versions.txt

docker run --rm --network none --entrypoint python3 botbox-experiment:ami --version
docker run --rm --network none --entrypoint pi botbox-pi:latest --version
docker run --rm --network none --entrypoint envoy envoyproxy/envoy:v1.36.2@sha256:4972515dd9a069b44beb43cebba7851596e72a8c61cd7a7c33d8f48efc5280ba --version
rm -rf /tmp/botbox-4fed2b153f15e216d9b07109355b83a6d7bdf819 /tmp/botbox.tar.gz /tmp/uv.tar.gz /tmp/uv-x86_64-unknown-linux-gnu /tmp/t-image /tmp/Dockerfile.t
apt-get clean
rm -rf /var/lib/apt/lists/*
