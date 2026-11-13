# Experimental SCHOOL-ONLY Webots runtime. This creates a distinct executable;
# the qualification physical binary, its Makefile, all source blobs and its
# generated-input SHA256 lock must remain byte-for-byte unchanged.
# This adapter is NOT the default product controller until native qualification.
C_SOURCES = ../crazyflie_runtime_v2/crazyflie_runtime_v2.c ../crazyflie_runtime_v2/runtime_entry.c ../crazyflie_runtime_v2/progression_sequence_evaluator.c ../crazyflie_runtime_v2/progression_precise_evaluator.c ../crazyflie_runtime_v2/progression_repeat_evaluator.c ../crazyflie_runtime_v2/progression_simple_decision_evaluator.c ../crazyflie_runtime_v2/progression_reactive_evaluator.c ../crazyflie_runtime_v2/progression_combined_decisions_evaluator.c ../crazyflie_runtime_v2/progression_autonomous_evaluator.c ../crazyflie_square/pid_controller.c
CFLAGS = -I../crazyflie_square -I../crazyflie_runtime_v2 -Dmain=webeeblocks_runtime_flight_main

# Firefox direct project files use the local Qt broker on supported desktop
# Webots builds. Windows follows Webots R2025a's own bundled Qt/MSYS2 layout;
# Linux uses the bundled Webots Qt libraries and plugin runtime environment.
ifeq ($(OS),Windows_NT)
 CXX_SOURCES = ../crazyflie_runtime_v2/file_broker.cpp ../crazyflie_runtime_v2/qt_file_dialog_provider.cpp ../crazyflie_runtime_v2/file_broker_runtime.cpp classroom_scene.cpp
 USE_C_API = true
 CFLAGS += -std=c++17 -D_USE_MATH_DEFINES -include ../crazyflie_runtime_v2/file_broker_interpose.h
 QT_INCLUDE_DIR = $(WEBOTS_HOME)/include/qt
 DYNAMIC_LIBRARIES += -L"$(WEBOTS_HOME)/msys64/mingw64/bin" -lQt6Core -lQt6Gui -lQt6Widgets -lole32 -luuid
 INCLUDE += -isystem "$(QT_INCLUDE_DIR)/QtCore" -isystem "$(QT_INCLUDE_DIR)/QtGui" -isystem "$(QT_INCLUDE_DIR)/QtWidgets"
else
 CXX_SOURCES = ../crazyflie_runtime_v2/file_broker.cpp ../crazyflie_runtime_v2/qt_file_dialog_provider.cpp ../crazyflie_runtime_v2/file_broker_runtime.cpp classroom_scene.cpp
 USE_C_API = true
 CFLAGS += -std=c++17 -fPIC -include ../crazyflie_runtime_v2/file_broker_interpose.h
 LDFLAGS += -pie
 QT_INCLUDE_DIR = $(WEBOTS_HOME)/include/qt
 DYNAMIC_LIBRARIES += -L"$(WEBOTS_HOME)/lib/webots" -lQt6Core -lQt6Gui -lQt6Widgets
 INCLUDE += -isystem "$(QT_INCLUDE_DIR)" -isystem "$(QT_INCLUDE_DIR)/QtCore" -isystem "$(QT_INCLUDE_DIR)/QtGui" -isystem "$(QT_INCLUDE_DIR)/QtWidgets"
endif

null :=
space := $(null) $(null)
WEBOTS_HOME_PATH?=$(subst $(space),\ ,$(strip $(subst \,/,$(WEBOTS_HOME))))
include $(WEBOTS_HOME_PATH)/resources/Makefile.include
