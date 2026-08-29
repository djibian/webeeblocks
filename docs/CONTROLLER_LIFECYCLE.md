# Simplified controller lifecycle

`Worker -> Ready PR -> exact-head CI -> Reviewer-Integrator -> GO -> merge`

If CI or review rejects the head:

`Ready PR -> Worker repair on same PR -> new SHA -> fresh CI -> Reviewer-Integrator`

No Ready→Draft→Ready loop is required. Every code change invalidates older verdicts by changing the exact head SHA.
