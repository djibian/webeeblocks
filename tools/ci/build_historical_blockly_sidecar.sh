#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
BOOST_ROOT="${WEBEEBLOCKS_HISTORICAL_BOOST_ROOT:-$ROOT/.ci-support/boost-1.74}"
IMAGE="cyberbotics/webots:R2025a-ubuntu22.04"

python3 "$ROOT/tools/ci/prepare_historical_boost.py" --output "$BOOST_ROOT" >/dev/null

test -f "$BOOST_ROOT/usr/include/boost/version.hpp"
grep -Eq '^#define BOOST_VERSION[[:space:]]+107400[[:space:]]*$' \
  "$BOOST_ROOT/usr/include/boost/version.hpp"

# The sidecar uses Boost.Asio/Beast headers and links only pthread on Linux.
# Keep the official Webots image while making the build itself offline and
# supplying only the verified read-only Boost header closure.
docker run --rm --network none \
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
  '
