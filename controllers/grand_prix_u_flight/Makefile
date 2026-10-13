.DEFAULT_GOAL := release
C_SOURCES = build/runtime_u.c ../crazyflie_square/pid_controller.c
CFLAGS = -I../crazyflie_square -I../crazyflie_runtime_v2 -I.
CXX_SOURCES = ../crazyflie_runtime_v2/file_broker.cpp ../crazyflie_runtime_v2/qt_file_dialog_provider.cpp build/file_broker_u.cpp grand_prix_u_deadline.cpp
USE_C_API = true
ifeq ($(OS),Windows_NT)
 CFLAGS += -std=c++17 -D_USE_MATH_DEFINES -include grand_prix_u_hook.h
 QT_INCLUDE_DIR = $(WEBOTS_HOME)/include/qt
 DYNAMIC_LIBRARIES += -L"$(WEBOTS_HOME)/msys64/mingw64/bin" -lQt6Core -lQt6Gui -lQt6Widgets -lole32 -luuid
 INCLUDE += -isystem "$(QT_INCLUDE_DIR)/QtCore" -isystem "$(QT_INCLUDE_DIR)/QtGui" -isystem "$(QT_INCLUDE_DIR)/QtWidgets"
else
 CFLAGS += -std=c++17 -fPIC -include grand_prix_u_hook.h
 LDFLAGS += -pie
 QT_INCLUDE_DIR = $(WEBOTS_HOME)/include/qt
 DYNAMIC_LIBRARIES += -L"$(WEBOTS_HOME)/lib/webots" -lQt6Core -lQt6Gui -lQt6Widgets
 INCLUDE += -isystem "$(QT_INCLUDE_DIR)" -isystem "$(QT_INCLUDE_DIR)/QtCore" -isystem "$(QT_INCLUDE_DIR)/QtGui" -isystem "$(QT_INCLUDE_DIR)/QtWidgets"
endif
CXX_SOURCES += $(wildcard ../crazyflie_runtime_v2/activity_scene.cpp)
null :=
space := $(null) $(null)
WEBOTS_HOME_PATH?=$(subst $(space),\ ,$(strip $(subst \,/,$(WEBOTS_HOME))))
build/runtime_u.c build/file_broker_u.cpp &: ../../tools/grand_prix/prepare_u_runtime.py ../crazyflie_runtime_v2/crazyflie_runtime_v2.c ../crazyflie_runtime_v2/file_broker_runtime.cpp
	python3 ../../tools/grand_prix/prepare_u_runtime.py
include $(WEBOTS_HOME_PATH)/resources/Makefile.include
