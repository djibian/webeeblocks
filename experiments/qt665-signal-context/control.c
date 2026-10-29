#include <signal.h>
#include <stdlib.h>
#include <string.h>
static void callback(int number) {
  (void)number;
  volatile char *p = malloc(120);
  if (!p) abort();
  *p = 1;
  free((void *)p);
}
int main(int argc, char **argv) {
  signal(SIGTERM, callback);
  if (argc == 2 && strcmp(argv[1], "signal") == 0) raise(SIGTERM);
  else callback(0);
  return 0;
}
