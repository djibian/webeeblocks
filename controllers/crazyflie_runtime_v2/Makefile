C_SOURCES = crazyflie_runtime_v2.c ../crazyflie_square/pid_controller.c
CFLAGS = -I../crazyflie_square
null :=
space := $(null) $(null)
WEBOTS_HOME_PATH?=$(subst $(space),\ ,$(strip $(subst \,/,$(WEBOTS_HOME))))
include $(WEBOTS_HOME_PATH)/resources/Makefile.include
