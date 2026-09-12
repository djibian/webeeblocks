C_SOURCES = crazyflie_runtime_v2.c ../crazyflie_square/pid_controller.c
CFLAGS = -I../crazyflie_square

# Firefox has no browser File System Access API. On a Linux desktop Webots SDK,
# compile the local Qt file broker and intercept only its dedicated WWI
# namespace. The official CI Docker image intentionally lacks the Qt headers,
# so the ordinary Runtime v2 build and Chrome path remain independent.
ifeq ($(shell uname -s 2>/dev/null),Linux)
ifneq ($(wildcard $(WEBOTS_HOME)/include/qt/QtWidgets/QFileDialog),)
 CXX_SOURCES += file_broker_runtime.cpp
 USE_C_API = true
 CFLAGS += -DWEBEEBLOCKS_NATIVE_FILE_BROKER -include file_broker_runtime.h
 QT_INCLUDE_DIR = $(WEBOTS_HOME)/include/qt
 DYNAMIC_LIBRARIES += -L"$(WEBOTS_HOME)/lib/webots" -lQt6Core -lQt6Gui -lQt6Widgets
 INCLUDE += -isystem "$(QT_INCLUDE_DIR)/QtCore" -isystem "$(QT_INCLUDE_DIR)/QtGui" -isystem "$(QT_INCLUDE_DIR)/QtWidgets"
endif
endif

null :=
space := $(null) $(null)
WEBOTS_HOME_PATH?=$(subst $(space),\ ,$(strip $(subst \,/,$(WEBOTS_HOME))))
include $(WEBOTS_HOME_PATH)/resources/Makefile.include
