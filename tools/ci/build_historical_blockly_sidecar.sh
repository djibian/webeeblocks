#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
BOOST_ROOT="${WEBEEBLOCKS_HISTORICAL_BOOST_ROOT:-$ROOT/.ci-support/boost-1.74}"
IMAGE="ghcr.io/djibian/webeeblocks-qt665-r2025a@sha256:7a9272dfef96e7668f8f31eaac9099b0417a9028e3181df6f8376eea59fe1aca"
WITH_SUPERVISOR=0

case "${1:-}" in
  "") ;;
  --with-supervisor) WITH_SUPERVISOR=1 ;;
  *) echo "usage: $0 [--with-supervisor]" >&2; exit 2 ;;
esac
if [ "$#" -gt 1 ]; then
  echo "usage: $0 [--with-supervisor]" >&2
  exit 2
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
