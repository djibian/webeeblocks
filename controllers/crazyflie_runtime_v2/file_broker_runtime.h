#ifndef WEBEEBLOCKS_FILE_BROKER_RUNTIME_H
#define WEBEEBLOCKS_FILE_BROKER_RUNTIME_H

#ifdef __cplusplus
extern "C" {
#endif
const char *webeeblocks_file_broker_receive_text(void);
#ifdef __cplusplus
}
#endif

#define wb_robot_wwi_receive_text webeeblocks_file_broker_receive_text

#endif
