#!/bin/sh
set -eu
# Botbox mounts a fresh credential home over the image's home directory.
cp /opt/u/models.json "$HOME/.pi/agent/"
exec pi --mode rpc --tools read,ls \
    --no-extensions \
    --no-skills --no-prompt-templates --no-themes --no-context-files "$@"
