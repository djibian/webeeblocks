# CI-only independent probe linked to the ACTUAL school scene selector.
# Never linked to the physically qualified flight controller.
CXX_SOURCES = progression_decision_h_scene_probe.cpp ../crazyflie_classroom_v2/classroom_scene.cpp
USE_C_API = true
CFLAGS += -std=c++17
null :=
space := $(null) $(null)
WEBOTS_HOME_PATH?=$(subst $(space),\ ,$(strip $(subst \,/,$(WEBOTS_HOME))))
include $(WEBOTS_HOME_PATH)/resources/Makefile.include
