#include <stdio.h>
#include <string.h>

int webeeblocks_progression_sequence_evaluator_main(void);

#define main webeeblocks_runtime_flight_main
#include "crazyflie_runtime_core.c"
#undef main

int main(int argc, char **argv) {
  if (argc == 2 && strcmp(argv[1], "sequence-evaluator-v1") == 0)
    return webeeblocks_progression_sequence_evaluator_main();
  if (argc != 1) {
    fprintf(stderr, "WEBEEBLOCKS_RUNTIME_V2 FATAL invalid controllerArgs\n");
    return 2;
  }
  return webeeblocks_runtime_flight_main();
}
