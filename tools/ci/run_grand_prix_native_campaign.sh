#!/usr/bin/env bash
# Dedicated manual diagnostic on this isolated branch; not CI Gate.
set -euo pipefail
[[ "$ACTIVITY" =~ ^[678]$ ]]
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
  python3 -u -m tools.ci.gp_native_latch_phase
  exit 0
fi
test "$(git -C ../webots-assets rev-parse HEAD)" = "$PROTO_SHA"
bash tools/prepare_runtime_v2.sh
python3 -m unittest tools.ci.test_grand_prix_route_v2 tools.ci.test_grand_prix_route_admission \
  tools.ci.test_a7_native_rebound tools.ci.test_gp_native_latch_phase
node --check tools/ci/grand_prix_progression_node_probe.js
mkdir -p ci-artifacts/grand-prix-u-geometry ci-artifacts/grand-prix-v2-h-native
if [[ "$ACTIVITY" == 8 ]]; then
  evidence=ci-artifacts/grand-prix-u-geometry/route-a8-native
  mkdir -p "$evidence"
  node tools/grand_prix/witness_workspace_a8.js "$evidence/pupil-project.wbb"
  node tools/grand_prix/witness_workspace_a8.js "$evidence/wrong-landing.wbb" --wrong-landing
  sha256sum "$evidence/"*.wbb
fi
export WEBEEBLOCKS_GP_GIT_HEAD="$(git rev-parse HEAD)"
export WEBEEBLOCKS_GP_GIT_TREE="$(git rev-parse HEAD^{tree})"
export WEBEEBLOCKS_GP_GIT_PARENTS="$(git cat-file -p HEAD | sed -n '/^$/q; s/^parent //p')"
export WEBEEBLOCKS_GP_GIT_STATUS="$(git status --porcelain --untracked-files=no)"
test "$WEBEEBLOCKS_GP_GIT_HEAD" = "$TARGET_SHA"
test -z "$WEBEEBLOCKS_GP_GIT_STATUS"
node_root="$(dirname "$(dirname "$(command -v node)")")"
image="$WEBOTS_OFFICIAL_IMAGE"
timeout -k 5s 480s docker pull "$image"
docker image inspect --format 'webots_image_id={{.Id}}' "$image"
docker run --rm --network host --shm-size=2g --entrypoint /bin/bash \
  -v "$PWD:/workspace" -w /workspace \
  -v "$(realpath "$0"):/opt/ci-campaign.sh:ro" \
  -v "$(realpath ../webots-assets/projects):/opt/ci-webots-projects:ro" \
  -v "$node_root:/opt/ci-node:ro" \
  -e ACTIVITY -e WEBOTS_HOME=/usr/local/webots \
  -e GITHUB_ACTIONS -e GITHUB_REPOSITORY -e GITHUB_WORKFLOW_SHA -e GITHUB_REF \
  -e GITHUB_RUN_ID -e GITHUB_RUN_ATTEMPT -e TARGET_SHA \
  -e WEBEEBLOCKS_GP_GIT_HEAD -e WEBEEBLOCKS_GP_GIT_TREE -e WEBEEBLOCKS_GP_GIT_PARENTS -e WEBEEBLOCKS_GP_GIT_STATUS \
  -e "WEBEEBLOCKS_GP_WEBOTS_IMAGE=$image" \
  -e LIBGL_ALWAYS_SOFTWARE=1 -e QTWEBENGINE_DISABLE_SANDBOX=1 \
  "$image" /opt/ci-campaign.sh --container
