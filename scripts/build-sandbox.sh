#!/usr/bin/env sh
set -eu

image="${1:-vaulty-sandbox:latest}"
script_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
repo_root=$(dirname -- "$script_dir")

docker build --tag "$image" "$repo_root"
