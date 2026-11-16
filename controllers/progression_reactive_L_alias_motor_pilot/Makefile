# Draft-only genuine Webots R2025a motor feasibility; NOT physical or pupil product.
# Preserve the locked product runtime/PID source verbatim. This is a separate
# test executable; only the scene admission and observational wrapper vary.
C_SOURCES = ../crazyflie_runtime_v2/crazyflie_runtime_v2.c ../crazyflie_runtime_v2/runtime_entry.c ../crazyflie_runtime_v2/progression_sequence_evaluator.c ../crazyflie_runtime_v2/progression_precise_evaluator.c ../crazyflie_runtime_v2/progression_repeat_evaluator.c ../crazyflie_runtime_v2/progression_simple_decision_evaluator.c ../crazyflie_runtime_v2/progression_reactive_evaluator.c ../crazyflie_runtime_v2/progression_combined_decisions_evaluator.c ../crazyflie_runtime_v2/progression_autonomous_evaluator.c ../crazyflie_square/pid_controller.c alias_motor_trace.c
CFLAGS = -I../crazyflie_square -I../crazyflie_runtime_v2 -Dmain=webeeblocks_runtime_flight_main
LFLAGS += -Wl,--wrap=wb_robot_step
CXX_SOURCES = ../crazyflie_runtime_v2/file_broker.cpp ../crazyflie_runtime_v2/qt_file_dialog_provider.cpp ../crazyflie_runtime_v2/file_broker_runtime.cpp alias_school_scene.cpp
USE_C_API = true
CFLAGS += -std=c++17 -fPIC -include ../crazyflie_runtime_v2/file_broker_interpose.h
LDFLAGS += -pie
QT_INCLUDE_DIR = $(WEBOTS_HOME)/include/qt
DYNAMIC_LIBRARIES += -L"$(WEBOTS_HOME)/lib/webots" -lQt6Core -lQt6Gui -lQt6Widgets
INCLUDE += -isystem "$(QT_INCLUDE_DIR)" -isystem "$(QT_INCLUDE_DIR)/QtCore" -isystem "$(QT_INCLUDE_DIR)/QtGui" -isystem "$(QT_INCLUDE_DIR)/QtWidgets"
null :=
space := $(null) $(null)
WEBOTS_HOME_PATH?=$(subst $(space),\ ,$(strip $(subst \,/,$(WEBOTS_HOME))))
include $(WEBOTS_HOME_PATH)/resources/Makefile.include
