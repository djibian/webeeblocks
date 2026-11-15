# A7 Draft probe links the actual SCHOOL-only SCENE admission gate.
# Not part of the physically qualified flight controller, no motor authority.
CXX_SOURCES = progression_mini_gp_scene_probe.cpp ../crazyflie_classroom_v2/classroom_scene.cpp
USE_C_API = true
CFLAGS += -std=c++17
null :=
space := $(null) $(null)
WEBOTS_HOME_PATH?=$(subst $(space),\ ,$(strip $(subst \,/,$(WEBOTS_HOME))))
include $(WEBOTS_HOME_PATH)/resources/Makefile.include
