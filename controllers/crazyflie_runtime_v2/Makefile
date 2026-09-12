C_SOURCES = crazyflie_runtime_v2.c ../crazyflie_square/pid_controller.c
CFLAGS = -I../crazyflie_square

# Firefox direct project files use a local Qt broker only on Linux desktop
# Webots. The Windows classroom release remains on the established C-only
# controller until its separate Firefox qualification is complete.
ifneq ($(OS),Windows_NT)
 CXX_SOURCES = file_broker.cpp qt_file_dialog_provider.cpp file_broker_runtime.cpp
 USE_C_API = true
 CFLAGS += -std=c++17 -fPIC -include file_broker_interpose.h
 LDFLAGS += -pie
 QT_INCLUDE_DIR = $(WEBOTS_HOME)/include/qt
 DYNAMIC_LIBRARIES += -L"$(WEBOTS_HOME)/lib/webots" -lQt6Core -lQt6Gui -lQt6Widgets
 INCLUDE += -isystem "$(QT_INCLUDE_DIR)" -isystem "$(QT_INCLUDE_DIR)/QtCore" -isystem "$(QT_INCLUDE_DIR)/QtGui" -isystem "$(QT_INCLUDE_DIR)/QtWidgets"
endif

null :=
space := $(null) $(null)
WEBOTS_HOME_PATH?=$(subst $(space),\ ,$(strip $(subst \,/,$(WEBOTS_HOME))))
include $(WEBOTS_HOME_PATH)/resources/Makefile.include
