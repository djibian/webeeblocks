# Source only in an isolated CI container. The PID must be a child launched with
# setsid by this shell: terminating xvfb-run alone leaves Webots running.
stop_webots_group() {
  local group_pid="$1"
  case "$group_pid" in ''|*[!0-9]*) return 1 ;; esac
  [ "$group_pid" -gt 1 ] || return 1
  kill -TERM -- "-$group_pid" 2>/dev/null || true
  # Give normal Webots cleanup a bounded grace period, then retire the group
  # before waiting: a TERM-resistant wrapper must not block the next attempt.
  for _ in 1 2 3 4 5 6 7 8 9 10; do
    kill -0 -- "-$group_pid" 2>/dev/null || break
    sleep .05
  done
  # A child can survive a parent's exit; retire only this owned session group.
  kill -KILL -- "-$group_pid" 2>/dev/null || true
  wait "$group_pid" 2>/dev/null || true
}
