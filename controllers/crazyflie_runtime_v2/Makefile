C_SOURCES = crazyflie_runtime_v2.c ../crazyflie_square/pid_controller.c
CFLAGS = -I../crazyflie_square
# #87 diagnostic-only Qt probe. Ordinary Runtime v2 builds remain unchanged.
ifeq ($(WEBEEBLOCKS_QT_INIT_DIAGNOSTIC),1)
 CXX_SOURCES = qt_init_probe.cpp
 USE_C_API = true
 CFLAGS += -std=c++17 -DWEBEEBLOCKS_QT_INIT_DIAGNOSTIC -g -O0
 QT_INCLUDE_DIR = $(WEBOTS_HOME)/include/qt
 DYNAMIC_LIBRARIES += -L"$(WEBOTS_HOME)/lib/webots" -lQt6Core -lQt6Gui -lQt6Widgets
 INCLUDE += -isystem "$(QT_INCLUDE_DIR)/QtCore" -isystem "$(QT_INCLUDE_DIR)/QtGui" -isystem "$(QT_INCLUDE_DIR)/QtWidgets"
endif

null :=
space := $(null) $(null)
WEBOTS_HOME_PATH?=$(subst $(space),\ ,$(strip $(subst \,/,$(WEBOTS_HOME))))
include $(WEBOTS_HOME_PATH)/resources/Makefile.include
