#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "${BASH_SOURCE[0]}")/.."
mkdir -p data
curl --fail --location --retry 3 \
  https://people.eecs.berkeley.edu/~hendrycks/APPS.tar.gz \
  --output data/APPS.tar.gz
tar -xzf data/APPS.tar.gz -C data
