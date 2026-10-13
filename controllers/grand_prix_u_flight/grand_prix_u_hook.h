#ifndef WEBEEBLOCKS_GP_U_HOOK_H
#define WEBEEBLOCKS_GP_U_HOOK_H
#ifdef __cplusplus
extern "C" {
#endif
int gp_u_start(double);
int gp_u_deadline(double, int);
int gp_u_next_step(int);
void gp_u_reset_complete(void);
int gp_u_filter_raw(const char *);
const char *gp_u_receive(void);
void gp_u_send(const char *, int);
#ifdef __cplusplus
}
#else
#define wb_robot_wwi_receive_text gp_u_receive
#define wb_robot_wwi_send gp_u_send
#define wb_robot_cleanup webeeblocks_file_broker_robot_cleanup
#endif
#endif
