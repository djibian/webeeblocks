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

  if [[ "$ACTIVITY" =~ ^[1-5]$ ]]; then
    # Reuse the canonical Runtime lesson runner, including the A4/A5
    # save/reopen and same-project digest witnesses. Keep its existing bounds.
    cap=600s
    if [[ "$ACTIVITY" =~ ^[45]$ ]]; then cap=1350s; fi
    timeout -k 5s "$cap" xvfb-run -a python3 -u tools/ci/run_grand_prix_u_geometry.py \
      --native --progression-activity "$ACTIVITY"
    evidence="ci-artifacts/grand-prix-u-geometry/route-a$ACTIVITY-native"
    test -s "$evidence/production-pilot-build.log"
    if [[ "$ACTIVITY" =~ ^[1-3]$ ]]; then
      for raw in world.wbt webots.log wwi.log pupil-reference.wbb pupil-project.wbb; do
        test -s "$evidence/$raw"
      done
      cmp "$evidence/pupil-reference.wbb" "$evidence/pupil-project.wbb"
    else
      count=3
      if [[ "$ACTIVITY" == 5 ]]; then count=5; fi
      test -s "$evidence/pupil-project.wbb"
      for ((variant=1; variant<=count; variant++)); do
        for raw in world.wbt webots.log wwi.log pupil-project.wbb; do
          test -s "ci-artifacts/grand-prix-u-geometry/route-a$ACTIVITY-v$variant-native/$raw"
        done
        cmp "$evidence/pupil-project.wbb" "ci-artifacts/grand-prix-u-geometry/route-a$ACTIVITY-v$variant-native/pupil-project.wbb"
      done
    fi
    exit 0
  fi

  python3 tools/grand_prix/prepare_route_runtime.py
  make -C controllers/grand_prix_route_flight 2>&1 | tee ci-artifacts/grand-prix-u-geometry/production-pilot-build.log
  test -x controllers/grand_prix_route_flight/grand_prix_route_flight

  if [[ "$ACTIVITY" == 8 ]]; then
    # Nominal and explicit wrong-pad project built once on the host.
    evidence=ci-artifacts/grand-prix-u-geometry/route-a8-native
    failures=0
    for ((variant=1; variant<=12; variant++)); do
      python3 -m tools.ci.run_grand_prix_progression_native --activity 8 --variant "$variant" \
        --pupil-project "$evidence/pupil-project.wbb" || failures=1
      out="ci-artifacts/grand-prix-u-geometry/route-a8-v$variant-native"
      for raw in world.wbt webots.log wwi.log trajectory.csv pupil-project.wbb wrong-landing.wbb; do
        test -s "$out/$raw" || failures=1
      done
      cmp "$evidence/pupil-project.wbb" "$out/pupil-project.wbb" || failures=1
      cmp "$evidence/wrong-landing.wbb" "$out/wrong-landing.wbb" || failures=1
    done
    exit "$failures"
  fi

  case "$ACTIVITY" in
    6) count=5 ;;
    7) count=7 ;;
    *) exit 2 ;;
  esac

  indexes=()
  for ((variant=1; variant<=count; variant++)); do
    indexes+=(--index "$variant")
  done

  # Preserve each independent witness even when an earlier one fails.
  failures=0
  if [[ "$ACTIVITY" == 7 && "${A7_PHASE_SWEEP:-0}" == 1 ]]; then
    python3 -m tools.ci.run_a7_rebound_phase || failures=1
  elif [[ "$ACTIVITY" == 7 ]]; then
    for rebound in stop liveness; do
      python3 -m tools.ci.run_grand_prix_progression_native \
        --activity 7 --variant 5 --rebound "$rebound" || failures=1
    done
  fi
  xvfb-run -a python3 tools/ci/run_grand_prix_v2_h_native.py --native \
    --activity "$ACTIVITY" "${indexes[@]}" || failures=1
  for ((variant=1; variant<=count; variant++)); do
    python3 -m tools.ci.run_grand_prix_progression_native \
      --activity "$ACTIVITY" --variant "$variant" || failures=1
    for raw in world.wbt webots.log wwi.log; do
      test -s "ci-artifacts/grand-prix-u-geometry/route-a$ACTIVITY-v$variant-native/$raw" || failures=1
    done
    if [[ "$ACTIVITY" == 7 ]]; then
      cmp ci-artifacts/grand-prix-u-geometry/a7-revised-reference.wbb \
        "ci-artifacts/grand-prix-u-geometry/route-a7-v$variant-native/a7-witness.wbb" || failures=1
    fi
  done
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
  1|2|3|4|5) image="$WEBOTS_M2_IMAGE" ;;
  6|7|8) image="$WEBOTS_OFFICIAL_IMAGE" ;;
  *) exit 2 ;;
esac

test "$(git -C ../webots-assets rev-parse HEAD)" = "$PROTO_SHA"
python3 -m unittest tools.ci.test_gp_multirate tools.ci.test_gp_multirate_reference
node_root="$(dirname "$(dirname "$(command -v node)")")"
if [[ "$ACTIVITY" =~ ^[1-5]$ ]]; then
  bash tools/prepare_runtime_v2.sh
elif [[ "$ACTIVITY" == 6 ]]; then
  bash tools/prepare_runtime_v2.sh
  python3 -m unittest tools.ci.test_grand_prix_route_v2 tools.ci.test_grand_prix_route_admission
  node tools/grand_prix/witness_workspace_a6.js
elif [[ "$ACTIVITY" == 7 ]]; then
  bash tools/prepare_runtime_v2.sh
  python3 -m unittest tools.ci.test_grand_prix_route_v2 tools.ci.test_grand_prix_route_admission \
    tools.ci.test_a7_retreat tools.ci.test_a7_native_rebound
  mkdir -p ci-artifacts/grand-prix-u-geometry
  node tools/grand_prix/witness_workspace_a7.js \
    ci-artifacts/grand-prix-u-geometry/a7-revised-reference.wbb --revised-geometry
fi

mkdir -p ci-artifacts/grand-prix-u-geometry ci-artifacts/grand-prix-v2-h-native
if [[ "$ACTIVITY" == 8 ]]; then
  bash tools/prepare_runtime_v2.sh
  evidence=ci-artifacts/grand-prix-u-geometry/route-a8-native
  mkdir -p "$evidence"
  node tools/grand_prix/witness_workspace_a8.js "$evidence/pupil-project.wbb"
  node tools/grand_prix/witness_workspace_a8.js "$evidence/wrong-landing.wbb" --wrong-landing
  sha256sum "$evidence/"*.wbb
fi
if [[ "$ACTIVITY" == 7 ]]; then
  export WEBEEBLOCKS_GP_GIT_HEAD="$(git rev-parse HEAD)"
  export WEBEEBLOCKS_GP_GIT_TREE="$(git rev-parse 'HEAD^{tree}')"
  # The candidate checkout can be shallow. Read the parents from the object.
  export WEBEEBLOCKS_GP_GIT_PARENTS="$(git cat-file -p HEAD | sed -n '/^$/q; s/^parent //p')"
  export WEBEEBLOCKS_GP_GIT_STATUS="$(git status --porcelain --untracked-files=no)"
  test "$WEBEEBLOCKS_GP_GIT_HEAD" = "$TARGET_SHA"
  test -z "$WEBEEBLOCKS_GP_GIT_STATUS"
fi
printf 'webots_image=%s\nnode=%s\n' "$image" "$(node --version)"
timeout -k 5s 480s docker pull "$image"
docker image inspect --format 'webots_image_id={{.Id}}' "$image"
docker run --rm --network host --shm-size=2g --entrypoint /bin/bash \
  -v "$PWD:/workspace" -w /workspace \
  -v "$(realpath "$0"):/opt/ci-campaign.sh:ro" \
  -v "$(realpath ../webots-assets/projects):/opt/ci-webots-projects:ro" \
  -v "$node_root:/opt/ci-node:ro" \
  -e ACTIVITY -e A7_PHASE_SWEEP -e WEBEEBLOCKS_GP_STEP_WALL_PROBE=1 -e WEBOTS_HOME=/usr/local/webots \
  -e GITHUB_ACTIONS -e GITHUB_REPOSITORY -e GITHUB_WORKFLOW_SHA -e GITHUB_REF \
  -e GITHUB_RUN_ID -e GITHUB_RUN_ATTEMPT -e TARGET_SHA \
  -e WEBEEBLOCKS_GP_GIT_HEAD -e WEBEEBLOCKS_GP_GIT_TREE \
  -e WEBEEBLOCKS_GP_GIT_PARENTS -e WEBEEBLOCKS_GP_GIT_STATUS \
  -e "WEBEEBLOCKS_GP_WEBOTS_IMAGE=$image" \
  -e LIBGL_ALWAYS_SOFTWARE=1 -e QTWEBENGINE_DISABLE_SANDBOX=1 \
  "$image" /opt/ci-campaign.sh --container
