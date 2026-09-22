#ifndef WEBEEBLOCKS_FILE_BROKER_INTERPOSE_H
#define WEBEEBLOCKS_FILE_BROKER_INTERPOSE_H

// The product controller remains C-only. On Linux desktop Webots builds with
// bundled Qt headers, interpose only its Robot Window transport/cleanup calls so
// broker and activity-outcome traffic can be consumed locally without changing
// Runtime v2 flight semantics or the C source.
#ifndef __cplusplus
#define wb_robot_wwi_receive_text webeeblocks_file_broker_receive_text
#define wb_robot_wwi_send webeeblocks_file_broker_send
#define wb_robot_cleanup webeeblocks_file_broker_robot_cleanup
#endif

#endif
