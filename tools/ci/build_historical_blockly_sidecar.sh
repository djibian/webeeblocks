#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
BOOST_ROOT="${WEBEEBLOCKS_HISTORICAL_BOOST_ROOT:-$ROOT/.ci-support/boost-1.74}"
IMAGE="ghcr.io/djibian/webeeblocks-qt665-r2025a@sha256:7a9272dfef96e7668f8f31eaac9099b0417a9028e3181df6f8376eea59fe1aca"
WITH_SUPERVISOR=0
PINNED_REFERENCE=0
for arg in "$@"; do
  case "$arg" in
    --with-supervisor)
      test "$WITH_SUPERVISOR" = 0 || { echo "duplicate --with-supervisor" >&2; exit 2; }
      WITH_SUPERVISOR=1 ;;
    --pinned-reference)
      test "$PINNED_REFERENCE" = 0 || { echo "duplicate --pinned-reference" >&2; exit 2; }
      PINNED_REFERENCE=1 ;;
    *) echo "usage: $0 [--with-supervisor] [--pinned-reference]" >&2; exit 2 ;;
  esac
done

# Only the explicitly selected #749 historical witnesses use the official
# R2025a reference, which must already have been pulled by exact digest.
# Never fetch a missing unqualified tag implicitly from Docker Hub.
if [ "$PINNED_REFERENCE" = 1 ]; then
  IMAGE="cyberbotics/webots:R2025a-ubuntu22.04"
  source_id="$(docker image inspect --format '{{.Id}}' "cyberbotics/webots@sha256:f0023e30daf38b172e4e6ad24ed345909bcd9551df34d63d824e121a7cebf099")"
  tag_id="$(docker image inspect --format '{{.Id}}' "$IMAGE")"
  if [[ ! "$source_id" =~ ^sha256:[[:xdigit:]]{64}$ || "$tag_id" != "$source_id" ]]; then
    echo "ERROR: historical sidecar image is not the pinned official R2025a source" >&2
    exit 1
  fi
fi

python3 "$ROOT/tools/ci/prepare_historical_boost.py" --output "$BOOST_ROOT" >/dev/null

test -f "$BOOST_ROOT/usr/include/boost/version.hpp"
grep -Eq '^#define BOOST_VERSION[[:space:]]+107400[[:space:]]*$' \
  "$BOOST_ROOT/usr/include/boost/version.hpp"

# The sidecar uses Boost.Asio/Beast headers and links only pthread on Linux.
# Keep the immutable qualified Webots image while keeping the build offline and
# supplying only the verified read-only Boost header closure. Historical jobs
# that also need the supervisor can request it in the same offline container.
docker run --rm --network none \
  -e WEBEEBLOCKS_BUILD_SUPERVISOR="$WITH_SUPERVISOR" \
  -v "$ROOT:/workspace" \
  -v "$BOOST_ROOT/usr/include:/opt/webeeblocks-boost/include:ro" \
  -w /workspace/controllers/supervisor/blocklyServer \
  "$IMAGE" \
  bash -lc '
    set -euo pipefail
    test -f /opt/webeeblocks-boost/include/boost/version.hpp
    grep -Eq "^#define BOOST_VERSION[[:space:]]+107400[[:space:]]*$" /opt/webeeblocks-boost/include/boost/version.hpp
    export CPLUS_INCLUDE_PATH=/opt/webeeblocks-boost/include
    rm -f blocklyServer
    make
    if [ "$WEBEEBLOCKS_BUILD_SUPERVISOR" = 1 ]; then
      cd /workspace/controllers/supervisor
      make clean
      make
    fi
  '
