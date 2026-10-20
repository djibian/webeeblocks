/* Experimental self-observation: no writes until a RESET decision. */
static char *diag_native_data, *diag_phase_data;
static size_t diag_native_size, diag_phase_size;
static FILE *diag_native, *diag_phase;
static int diag_error;
static void diag_number(FILE *f, double x) {
  if (isfinite(x)) fprintf(f, "%.17g", x);
  else fprintf(f, "\"%s\"", isnan(x) ? "nan" : x > 0 ? "inf" : "-inf");
}
static void diag_array(FILE *f, const double *a, int n) {
  fputc('[', f);
  for (int i=0;i<n;i++) { if(i) fputc(',',f); diag_number(f,a[i]); }
  fputc(']',f);
}
static void diag_string(FILE *f, const char *s) {
  fputc('"',f);
  for (;*s;s++) {
    unsigned char c=(unsigned char)*s;
    if(c=='"' || c=='\\') fputc('\\',f);
    if(c<32) fprintf(f,"\\u%04x",c); else fputc(c,f);
  }
  fputc('"',f);
}
static void diag_open(void) {
  diag_native=open_memstream(&diag_native_data,&diag_native_size);
  diag_phase=open_memstream(&diag_phase_data,&diag_phase_size);
  if(!diag_native || !diag_phase) { fprintf(stderr,"BUFFER_PREPARATION_ERROR\n"); exit(91); }
}
static void diag_sample(WbNodeRef node, double now, const double *gps_values,
                        const double *angles, const double *gyro_values,
                        WbDeviceTag m1,WbDeviceTag m2,WbDeviceTag m3,WbDeviceTag m4) {
  fprintf(diag_native,"{\"type\":\"sample\",\"time\":%.9f,\"custom_data\":",now);
  diag_string(diag_native,wb_robot_get_custom_data());
  fputs(",\"position\":",diag_native); diag_array(diag_native,wb_supervisor_node_get_position(node),3);
  fputs(",\"orientation\":",diag_native); diag_array(diag_native,wb_supervisor_node_get_orientation(node),9);
  fputs(",\"velocity\":",diag_native); diag_array(diag_native,wb_supervisor_node_get_velocity(node),6);
  int count=0; WbContactPoint *contacts=wb_supervisor_node_get_contact_points(node,true,&count);
  fputs(",\"contacts\":[",diag_native);
  for(int i=0;i<count;i++) {
    if(i) fputc(',',diag_native);
    fputs("{\"point\":",diag_native); diag_array(diag_native,contacts[i].point,3);
    fprintf(diag_native,",\"node_id\":%d}",contacts[i].node_id);
  }
  fputs("],\"sensor_gps\":",diag_native); diag_array(diag_native,gps_values,3);
  fputs(",\"sensor_rpy\":",diag_native); diag_array(diag_native,angles,3);
  fputs(",\"sensor_gyro\":",diag_native); diag_array(diag_native,gyro_values,3);
  double targets[4]={wb_motor_get_velocity(m1),wb_motor_get_velocity(m2),wb_motor_get_velocity(m3),wb_motor_get_velocity(m4)};
  fputs(",\"motor_targets\":",diag_native); diag_array(diag_native,targets,4);
  fputs("}\n",diag_native);
  if(ftell(diag_native)>128*1024*1024) { fprintf(stderr,"BUFFER_CAPACITY_ERROR\n"); exit(92); }
}
static void diag_dump(void) {
  /* Called only after the unchanged Runtime has selected OK or timeout. */
  fflush(diag_native); fflush(diag_phase);
  const char *dir=getenv("WEBEEBLOCKS_CI_ARTIFACT_DIR"); char path[2048];
  if(!dir) {fprintf(stderr,"BUFFER_DIRECTORY_ERROR\n");exit(93);}
  snprintf(path,sizeof(path),"%s/native-reset-state.jsonl",dir);
  FILE *f=fopen(path,"a"); if(!f) exit(94);
  if(ftell(f)==0) fputs("{\"type\":\"header\",\"version\":1,\"step_ms\":32,\"scope\":\"read-only-native-state-not-runtime-ack\"}\n",f);
  if(fwrite(diag_native_data,1,diag_native_size,f)!=diag_native_size) diag_error=1;
  if(fclose(f)) diag_error=1;
  snprintf(path,sizeof(path),"%s/buffered-phase.log",dir);
  f=fopen(path,"a"); if(!f) exit(95);
  if(fwrite(diag_phase_data,1,diag_phase_size,f)!=diag_phase_size) diag_error=1;
  if(fclose(f)) diag_error=1;
  fclose(diag_native); fclose(diag_phase);
  free(diag_native_data);free(diag_phase_data);
  diag_native_data=diag_phase_data=NULL;diag_native_size=diag_phase_size=0;
  if(diag_error) exit(96);
  diag_open();
}
