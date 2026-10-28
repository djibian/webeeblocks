#!/usr/bin/env bash
# Issue #747: keep the official R2025a historical image byte-identified while
# bounding external preparation separately from the 30s in-container oracle.
set -euo pipefail
IMAGE="cyberbotics/webots"
TAG="R2025a-ubuntu22.04"
DIGEST="sha256:f0023e30daf38b172e4e6ad24ed345909bcd9551df34d63d824e121a7cebf099"
SOURCE="${IMAGE}@${DIGEST}"
TARGET="${IMAGE}:${TAG}"

# Never turn a slow external pull into a green/skipped historical oracle.
timeout -k 5s 480s docker pull "$SOURCE"
source_id="$(docker image inspect --format '{{.Id}}' "$SOURCE")"
if [[ ! "$source_id" =~ ^sha256:[[:xdigit:]]{64}$ ]]; then
  echo "ERROR: no valid pinned historical Webots image ID" >&2
  exit 1
fi

# Legacy native tests and build scripts still consume the exact R2025a tag.
docker tag "$SOURCE" "$TARGET"
tag_id="$(docker image inspect --format '{{.Id}}' "$TARGET")"
if [[ "$tag_id" != "$source_id" ]]; then
  echo "ERROR: pinned historical Webots image identity mismatch" >&2
  exit 1
fi
printf 'PASS exact historical Webots R2025a OCI manifest %s; local image %s\n' "$DIGEST" "$source_id"
