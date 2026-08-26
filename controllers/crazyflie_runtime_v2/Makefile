C_SOURCES = crazyflie_runtime_v2.c ../crazyflie_square/pid_controller.c
CFLAGS = -I../crazyflie_square

# 71-C3 keeps the native broker out of ordinary Runtime v2 builds. Only the
# desktop-SDK proof gate opts in, so Docker-based product gates remain causal.
ifeq ($(WEBEEBLOCKS_NATIVE_FILE_BROKER),1)
 CXX_SOURCES = file_broker.cpp
 USE_C_API = true
 CFLAGS += -std=c++17 -DWEBEEBLOCKS_NATIVE_FILE_BROKER
 QT_INCLUDE_DIR = $(WEBOTS_HOME)/include/qt
 DYNAMIC_LIBRARIES += -L"$(WEBOTS_HOME)/lib/webots" -lQt6Core -lQt6Gui -lQt6Widgets
 INCLUDE += -isystem "$(QT_INCLUDE_DIR)/QtCore" -isystem "$(QT_INCLUDE_DIR)/QtGui" -isystem "$(QT_INCLUDE_DIR)/QtWidgets"
endif

# C10 diagnostic rendezvous is compiled only by the dedicated desktop-SDK
# workflow. Ordinary Runtime v2 builds contain neither the pause nor debug flags.
ifeq ($(WEBEEBLOCKS_QT_CRASH_DIAGNOSTIC),1)
 CFLAGS += -DWEBEEBLOCKS_QT_CRASH_DIAGNOSTIC -g -O0
endif
null :=
space := $(null) $(null)
WEBOTS_HOME_PATH?=$(subst $(space),\ ,$(strip $(subst \,/,$(WEBOTS_HOME))))
include $(WEBOTS_HOME_PATH)/resources/Makefile.include
