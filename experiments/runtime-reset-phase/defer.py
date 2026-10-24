"""Experimental timing intervention only: release the seventh RESET N steps later."""


def receiver(steps):
    if steps not in (1, 8, 16):
        raise ValueError("only preregistered 1/8/16 native-step delays are supported")
    return r'''
static const char *reset_phase_receive(void) {
  static unsigned reset_count = 0;
  static char deferred[256];
  static int deferred_id = -1;
  static double release_at = -1.0;
  const double time = wb_robot_get_time();
  if (release_at >= 0.0) {
    if (time + 1e-9 < release_at)
      return NULL;
    release_at = -1.0;
    fprintf(stderr, PREFIX " RESET_DEFER_RELEASE id=%d time=%.9f\n", deferred_id, time);
    return deferred;
  }
  const char *message = wb_robot_wwi_receive_text();
  int id = -1, consumed = 0;
  if (message && sscanf(message, PREFIX " REQUEST %d RESET%n", &id, &consumed) == 1 &&
      id > 0 && consumed > 0 && message[consumed] == '\0') {
    ++reset_count;
    if (reset_count == 7 && strlen(message) < sizeof(deferred)) {
      strcpy(deferred, message);
      deferred_id = id;
      release_at = time + DELAY_STEPS * wb_robot_get_basic_time_step() * 0.001;
      fprintf(stderr, PREFIX " RESET_DEFER_BEGIN id=%d time=%.9f steps=DELAY_STEPS\n", id, time);
      return NULL;
    }
  }
  return message;
}
'''.replace("DELAY_STEPS", str(steps))


def defer(source, steps):
    anchor = "#define ACTION_TIMEOUT 25.0\n"
    receive = "while ((message = wb_robot_wwi_receive_text()) != NULL) {"
    if source.count(anchor) != 1 or source.count(receive) != 1:
        raise ValueError("unrecognized original receiver; refuse timing intervention")
    return source.replace(anchor, anchor + receiver(steps), 1).replace(
        receive, "while ((message = reset_phase_receive()) != NULL) {", 1)
