# Controller PR state rules

Draft/Ready is not a role lock. New controller PRs normally open Ready after branch-side preparation. A failing or rejected Ready PR is repaired directly on the same PR; the new SHA invalidates stale verdicts and triggers fresh CI.
