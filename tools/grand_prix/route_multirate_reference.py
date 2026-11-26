"""G2 route-only 32-ms horizontal/yaw reference knots, 8-ms feedback."""

REFERENCE = r'''
/* Cache the analytic trajectory, not a measured pose or a safety decision.
 * Each 32-ms segment is interpolated at the native 8-ms pilot tick.
 * A command/epoch transition rebuilds the cache; the exact endpoint and
 * original reference duration remain authoritative for completion. */
typedef struct {
  int valid, mode, request;
  long long segment;
  double start, distance, limit, duration, lo, hi, f0, f1, v0, v1;
  unsigned long long calls, knots;
} gp_reference_cache_t;

static void gp_reference_cached(gp_reference_cache_t *c, int mode, int request,
                                double start, double now, double distance, double limit,
                                double *fraction, double *speed, double *duration) {
  const double elapsed = fmax(0.0, now - start);
  const long long segment = llround(elapsed * 1000.0) / 32;
  const int same = c->valid && c->mode == mode && c->request == request &&
                   c->start == start && c->distance == distance && c->limit == limit;
  ++c->calls;
  if (!same || (segment != c->segment && elapsed < c->duration)) {
    const double lo = segment * 0.032;
    if (same && segment == c->segment + 1 && c->hi == lo) {
      c->f0 = c->f1; c->v0 = c->v1;
    } else {
      gp_motion_reference(distance, limit, lo, &c->f0, &c->v0, &c->duration);
      ++c->knots;
    }
    c->lo = lo;
    c->hi = fmin(c->duration, (segment + 1) * 0.032);
    gp_motion_reference(distance, limit, c->hi, &c->f1, &c->v1, &c->duration);
    ++c->knots;
    c->valid = 1; c->mode = mode; c->request = request; c->segment = segment;
    c->start = start; c->distance = distance; c->limit = limit;
  }
  *duration = c->duration;
  if (elapsed >= c->duration) { *fraction = 1.0; *speed = 0.0; return; }
  const double u = fmin(1.0, fmax(0.0, (elapsed - c->lo) / (c->hi - c->lo)));
  *fraction = fmin(1.0, fmax(0.0, c->f0 + u * (c->f1 - c->f0)));
  *speed = fmin(limit, fmax(0.0, c->v0 + u * (c->v1 - c->v0)));
}
'''


def compose(source):
    edits = (
        ('static double wrap_angle(double angle) {',
         REFERENCE + '\nstatic double wrap_angle(double angle) {'),
        ('  gp_multirate_t gp_xy = {0};',
         '  gp_multirate_t gp_xy = {0};\n  gp_reference_cache_t gp_ref = {0};'),
        ('        memset(&gp_xy, 0, sizeof(gp_xy));',
         '        memset(&gp_xy, 0, sizeof(gp_xy));\n'
         '        memset(&gp_ref, 0, sizeof(gp_ref));'),
        ('      gp_motion_reference(active_value, move_speed_limit, now - action_start,',
         '      gp_reference_cached(&gp_ref, command, active_id, action_start, now,\n'
         '                          active_value, move_speed_limit,'),
        ('      gp_motion_reference(fabs(angle), YAW_RATE_MAX, now - action_start,',
         '      gp_reference_cached(&gp_ref, command, active_id, action_start, now,\n'
         '                          fabs(angle), YAW_RATE_MAX,'),
        ('               gp_xy.ticks, gp_xy.updates);',
         '               gp_xy.ticks, gp_xy.updates);\n'
         '        printf("GP_ROUTE_REFERENCE calls=%llu knots=%llu period_ms=32\\n",\n'
         '               gp_ref.calls, gp_ref.knots);'),
    )
    for old, new in edits:
        if source.count(old) != 1:
            raise RuntimeError('route reference cache anchor drift')
        source = source.replace(old, new, 1)
    return source
