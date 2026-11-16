/* A7 Draft R2025a: exercise the ACTUAL school scene importer L->R->L.
 * Never starts motors or pupil AST. Rejects duplicate, residual or wrongly
 * typed observation nodes; refuses unknown scenes without losing current.
 */
#include "../crazyflie_runtime_v2/activity_scene.h"
#include "../crazyflie_classroom_v2/mini_gp_scene_gate.h"
#include <webots/robot.h>
#include <webots/supervisor.h>
#include <cstdio>
#include <cstring>

static int fail(const char *why){
  std::fprintf(stderr,"WEBEEBLOCKS_A7_SCENE_SELECTOR_FATAL %s\n",why);
  std::fflush(stderr);wb_robot_cleanup();return 2;
}
static bool settle(int step){
  for(int i=0;i<16;++i)if(wb_robot_step(step)<0)return false;
  return true;
}
static bool only(char variant){
  const char *want=variant=='L'?"WEBEEBLOCKS_MINI_GP_L_SCENE":
                                 "WEBEEBLOCKS_MINI_GP_R_SCENE";
  const char *other=variant=='L'?"WEBEEBLOCKS_MINI_GP_R_SCENE":
                                  "WEBEEBLOCKS_MINI_GP_L_SCENE";
  return wb_supervisor_node_get_from_def(want)!=nullptr &&
         wb_supervisor_node_get_from_def(other)==nullptr &&
         webeeblocks_a7_gate::valid(variant) &&
         webeeblocks_activity_scene_ready();
}
int main(void){
  wb_robot_init();
  const int step=(int)wb_robot_get_basic_time_step();
  const char *name=wb_robot_get_name();
  if(step!=32||!name||std::strcmp(name,"A7 native selector test")||
     wb_supervisor_node_get_from_def("WEBEEBLOCKS_MINI_GP_L_SCENE")||
     wb_supervisor_node_get_from_def("WEBEEBLOCKS_MINI_GP_R_SCENE")||
     webeeblocks_activity_scene_ready())
    return fail("startup precondition or spurious empty READY");
  if(webeeblocks_select_activity_scene("mini-grand-prix-x-v1") ||
     webeeblocks_activity_scene_ready())
    return fail("untrusted token accepted in empty world");
  if(!webeeblocks_select_activity_scene("mini-grand-prix-l-v1")||
     !only('L')||!settle(step))
    return fail("L import, exact colliders or native observer invalid");
  std::puts("WEBEEBLOCKS_A7_SCENE_SELECTOR_ACK variant=L generation=1");
  std::fflush(stdout);
  if(!webeeblocks_select_activity_scene("mini-grand-prix-r-v1")||
     !only('R')||!settle(step))
    return fail("R import failed or L leaked across scene swap");
  std::puts("WEBEEBLOCKS_A7_SCENE_SELECTOR_ACK variant=R generation=1");
  std::fflush(stdout);
  if(!webeeblocks_select_activity_scene("mini-grand-prix-l-v1")||
     !only('L')||!settle(step))
    return fail("L re-import failed or previous R observer survived");
  std::puts("WEBEEBLOCKS_A7_SCENE_SELECTOR_ACK variant=L generation=2");
  std::fflush(stdout);
  if(webeeblocks_select_activity_scene("unknown-scene-token")||!only('L'))
    return fail("unknown token corrupted a valid current selection");
  std::puts("WEBEEBLOCKS_A7_SCENE_SELECTOR_NATIVE_PASS L-R-L ready=attested motors=OFF pupil=UNPROVEN");
  std::fflush(stdout);
  wb_robot_cleanup();return 0;
}
