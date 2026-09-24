#ifdef main
#undef main
#endif

#include <stdio.h>
#include <string.h>

int webeeblocks_runtime_flight_main(void);
int webeeblocks_progression_sequence_evaluator_main(void);
int webeeblocks_progression_precise_evaluator_main(void);
int webeeblocks_progression_repeat_evaluator_main(void);
int webeeblocks_progression_simple_decision_evaluator_main(void);
int webeeblocks_progression_reactive_evaluator_main(void);
int webeeblocks_progression_combined_decisions_evaluator_main(void);

int main(int argc, char **argv) {
  if (argc == 2 && strcmp(argv[1], "sequence-evaluator-v1") == 0)
    return webeeblocks_progression_sequence_evaluator_main();
  if (argc == 2 && strcmp(argv[1], "precise-evaluator-v1") == 0)
    return webeeblocks_progression_precise_evaluator_main();
  if (argc == 2 && strcmp(argv[1], "repeat-evaluator-v1") == 0)
    return webeeblocks_progression_repeat_evaluator_main();
  if (argc == 2 && strcmp(argv[1], "simple-decision-evaluator-v1") == 0)
    return webeeblocks_progression_simple_decision_evaluator_main();
  if (argc == 2 && strcmp(argv[1], "reactive-evaluator-v1") == 0)
    return webeeblocks_progression_reactive_evaluator_main();
  if (argc == 2 && strcmp(argv[1], "combined-decisions-evaluator-v1") == 0)
    return webeeblocks_progression_combined_decisions_evaluator_main();
  if (argc != 1) {
    fprintf(stderr, "WEBEEBLOCKS_RUNTIME_V2 FATAL invalid controllerArgs\n");
    return 2;
  }
  return webeeblocks_runtime_flight_main();
}
