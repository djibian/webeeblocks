#ifndef WEBEEBLOCKS_FILE_BROKER_C_H
#define WEBEEBLOCKS_FILE_BROKER_C_H

#ifdef __cplusplus
extern "C" {
#endif

typedef struct WbFileBroker WbFileBroker;

WbFileBroker *wb_file_broker_create_qt(void);
void wb_file_broker_destroy(WbFileBroker *broker);
// Returns NULL when the message is not for the broker. The returned string is
// owned by broker and remains valid until the next broker call or destruction.
const char *wb_file_broker_handle_message(WbFileBroker *broker, const char *message);

#ifdef __cplusplus
}
#endif
#endif
