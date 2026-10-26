/* Copied under several different Webots stub header filenames by pose tests. */
#ifndef WEBEEBLOCKS_GP_U_POSE_WEBOTS_STUB_H
#define WEBEEBLOCKS_GP_U_POSE_WEBOTS_STUB_H
#include <stdbool.h>
#ifdef __cplusplus
extern "C" {
#endif
typedef int WbDeviceTag; typedef void* WbNodeRef; typedef void* WbFieldRef;
typedef struct { double point[3]; int node_id; } WbContactPoint;
WbContactPoint* wb_supervisor_node_get_contact_points(WbNodeRef,bool,int*);
void wb_robot_init(void);void wb_robot_cleanup(void);int wb_robot_step(int);
double wb_robot_get_time(void); double wb_robot_get_basic_time_step(void);
WbDeviceTag wb_robot_get_device(const char*);
const char* wb_robot_wwi_receive_text(void);void wb_robot_wwi_send(const char*,int);
static inline void wb_robot_wwi_send_text(const char* s){int n=0;while(s[n])++n;wb_robot_wwi_send(s,n+1);}
void wb_motor_set_position(int,double);void wb_motor_set_velocity(int,double);
void wb_gps_enable(int,int);void wb_gyro_enable(int,int);void wb_inertial_unit_enable(int,int);void wb_distance_sensor_enable(int,int);
const double* wb_gps_get_values(int);const double* wb_gyro_get_values(int);const double* wb_inertial_unit_get_roll_pitch_yaw(int);
double wb_distance_sensor_get_value(int);void wb_led_set(int,int);
WbNodeRef wb_supervisor_node_get_self(void);WbNodeRef wb_supervisor_node_get_from_def(const char*);
WbFieldRef wb_supervisor_node_get_field(WbNodeRef,const char*);
const char* wb_supervisor_field_get_sf_string(WbFieldRef);void wb_supervisor_field_set_sf_string(WbFieldRef,const char*);
const double* wb_supervisor_field_get_sf_vec3f(WbFieldRef);const double* wb_supervisor_field_get_sf_rotation(WbFieldRef);
void wb_supervisor_field_set_sf_vec3f(WbFieldRef,const double*);void wb_supervisor_field_set_sf_rotation(WbFieldRef,const double*);
void wb_supervisor_node_reset_physics(WbNodeRef);
const char* wb_robot_get_project_path(void);
WbNodeRef wb_supervisor_node_get_root(void);
const char* wb_supervisor_node_get_type_name(WbNodeRef);
const char* wb_supervisor_node_get_def(WbNodeRef);
const char* wb_supervisor_node_export_string(WbNodeRef);
void wb_supervisor_node_remove(WbNodeRef);
int wb_supervisor_field_get_count(WbFieldRef);
WbNodeRef wb_supervisor_field_get_mf_node(WbFieldRef,int);
void wb_supervisor_field_import_mf_node_from_string(WbFieldRef,int,const char*);
#ifdef __cplusplus
}
#endif

#endif /* WEBEEBLOCKS_GP_U_POSE_WEBOTS_STUB_H */
