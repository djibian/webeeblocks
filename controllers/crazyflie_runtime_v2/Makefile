C_SOURCES = crazyflie_runtime_v2.c ../crazyflie_square/pid_controller.c
CFLAGS = -I../crazyflie_square

# Firefox direct project files use the local Qt broker on supported desktop
# Webots controller builds. Keep the product controller C source unchanged and
# interpose only its WWI receive/cleanup calls; the broker/provider stay in C++.
ifeq ($(OS),Windows_NT)
 CXX_SOURCES = file_broker.cpp qt_file_dialog_provider.cpp file_broker_runtime.cpp
 USE_C_API = true
 CFLAGS += -std=c++17 -D_USE_MATH_DEFINES -include file_broker_interpose.h
 QT_INCLUDE_DIR = $(WEBOTS_HOME)/include/qt
 DYNAMIC_LIBRARIES += -L"$(WEBOTS_HOME)/msys64/mingw64/bin" -lQt6Core -lQt6Gui -lQt6Widgets
 INCLUDE += -isystem "$(QT_INCLUDE_DIR)" -isystem "$(QT_INCLUDE_DIR)/QtCore" -isystem "$(QT_INCLUDE_DIR)/QtGui" -isystem "$(QT_INCLUDE_DIR)/QtWidgets"
else ifeq ($(shell uname -s),Linux)
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
