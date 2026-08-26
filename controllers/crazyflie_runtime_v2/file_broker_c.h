#ifndef WEBEEBLOCKS_FILE_BROKER_C_H
#define WEBEEBLOCKS_FILE_BROKER_C_H

#include <stddef.h>

#ifdef __cplusplus
extern "C" {
#endif

typedef struct WbFileBroker WbFileBroker;
WbFileBroker *wb_file_broker_create_qt(void);
void wb_file_broker_destroy(WbFileBroker *broker);
int wb_file_broker_handle_message(const WbFileBroker *broker, const char *message, char *response,
                                  size_t response_size);

#ifdef __cplusplus
}
#endif
#endif
