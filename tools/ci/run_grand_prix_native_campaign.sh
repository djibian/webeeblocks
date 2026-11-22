#!/usr/bin/env bash
# Runs in the exact candidate checkout. The workflow supplies the harness,
# activity and pinned external inputs independently of that checkout.
set -euo pipefail

if [[ "${1:-}" == --container ]]; then
  export PATH="/opt/ci-node/bin:$PATH"
  [[ "$(node --version)" == v22.* ]]
  test "$(cat "$WEBOTS_HOME/resources/version.txt")" = R2025a
  for proto in robots/bitcraze/crazyflie/protos/Crazyflie.proto \
      objects/backgrounds/protos/TexturedBackground.proto \
      objects/backgrounds/protos/TexturedBackgroundLight.proto \
      objects/floors/protos/Floor.proto appearances/protos/Parquetry.proto; do
    test -s "/opt/ci-webots-projects/$proto"
  done
  mkdir -p "$WEBOTS_HOME/projects"
  cp -a /opt/ci-webots-projects/. "$WEBOTS_HOME/projects/"

  if [[ "$ACTIVITY" =~ ^[1-3]$ ]]; then
    # Invoke the existing Runtime entry inside M2, with Node available to its
    # exact native WWI runner. Keep the Runtime campaign's 600-second bound.
    timeout -k 5s 600s xvfb-run -a python3 -u tools/ci/run_grand_prix_u_geometry.py \
      --native --progression-activity "$ACTIVITY"
    for raw in production-pilot-build.log world.wbt webots.log wwi.log; do
      test -s "ci-artifacts/grand-prix-u-geometry/route-a$ACTIVITY-native/$raw"
    done
    exit 0
  fi

  python3 tools/grand_prix/prepare_route_runtime.py
  make -C controllers/grand_prix_route_flight 2>&1 | tee ci-artifacts/grand-prix-u-geometry/production-pilot-build.log
  test -x controllers/grand_prix_route_flight/grand_prix_route_flight

  case "$ACTIVITY" in
    4) count=3 ;;
    5|6) count=5 ;;
    7) count=7 ;;
    *) exit 2 ;;
  esac

  indexes=()
  for ((variant=1; variant<=count; variant++)); do
    indexes+=(--index "$variant")
  done

  # Preserve each independent witness even when an earlier one fails.
  failures=0
  xvfb-run -a python3 tools/ci/run_grand_prix_v2_h_native.py --native \
    --activity "$ACTIVITY" "${indexes[@]}" || failures=1
  for ((variant=1; variant<=count; variant++)); do
    python3 -m tools.ci.run_grand_prix_progression_native \
      --activity "$ACTIVITY" --variant "$variant" || failures=1
    for raw in world.wbt webots.log wwi.log; do
      test -s "ci-artifacts/grand-prix-u-geometry/route-a$ACTIVITY-v$variant-native/$raw" || failures=1
    done
  done
  if [[ "$ACTIVITY" == 7 ]]; then
    # All seven native variants must share byte-identical saved pupil code.
    first=""
    for variant in {1..7}; do
      file="ci-artifacts/grand-prix-u-geometry/route-a7-v${variant}-native/a7-witness.wbb"
      if [[ ! -s "$file" ]]; then failures=1; continue; fi
      digest="$(sha256sum "$file" | awk '{print $1}')"
      if [[ -n "$first" && "$first" != "$digest" ]]; then failures=1; fi
      first="$digest"
    done
    if [[ "$failures" == 0 ]]; then printf 'A7_SAME_WBB_SHA256=%s\n' "$first"; fi
  fi
  if [[ "$ACTIVITY" == 6 ]]; then
    for variant in 4 5; do
      WEBEEBLOCKS_A6_SHALLOW_CONTACT_DIAGNOSTIC=1 python3 -m tools.ci.run_grand_prix_progression_native \
        --activity 6 --variant "$variant" || failures=1
    done
    python3 tools/ci/check_a6_native_evidence.py || failures=1
  fi
  exit "$failures"
fi

case "$ACTIVITY" in
  1|2|3) image="$WEBOTS_M2_IMAGE" ;;
  4|5|6|7) image="$WEBOTS_OFFICIAL_IMAGE" ;;
  *) exit 2 ;;
esac

test "$(git -C ../webots-assets rev-parse HEAD)" = "$PROTO_SHA"
node_root="$(dirname "$(dirname "$(command -v node)")")"
if [[ "$ACTIVITY" == 6 || "$ACTIVITY" == 7 ]]; then
  bash tools/prepare_runtime_v2.sh
  python3 -m unittest tools.ci.test_grand_prix_route_v2 tools.ci.test_grand_prix_route_admission
  node "tools/grand_prix/witness_workspace_a${ACTIVITY}.js"
fi

mkdir -p ci-artifacts/grand-prix-u-geometry ci-artifacts/grand-prix-v2-h-native
printf 'webots_image=%s\nnode=%s\n' "$image" "$(node --version)"
timeout -k 5s 480s docker pull "$image"
docker image inspect --format 'webots_image_id={{.Id}}' "$image"
docker run --rm --network host --shm-size=2g --entrypoint /bin/bash \
  -v "$PWD:/workspace" -w /workspace \
  -v "$(realpath "$0"):/opt/ci-campaign.sh:ro" \
  -v "$(realpath ../webots-assets/projects):/opt/ci-webots-projects:ro" \
  -v "$node_root:/opt/ci-node:ro" \
  -e ACTIVITY -e WEBOTS_HOME=/usr/local/webots \
  -e "WEBEEBLOCKS_GP_WEBOTS_IMAGE=$image" \
  -e LIBGL_ALWAYS_SOFTWARE=1 -e QTWEBENGINE_DISABLE_SANDBOX=1 \
  "$image" /opt/ci-campaign.sh --container
