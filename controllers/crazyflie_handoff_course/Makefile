C_SOURCES = crazyflie_handoff_course.c ../crazyflie_square/pid_controller.c
CFLAGS = -I../crazyflie_square -I../crazyflie_square_position

null :=
space := $(null) $(null)
WEBOTS_HOME_PATH?=$(subst $(space),\ ,$(strip $(subst \,/,$(WEBOTS_HOME))))
include $(WEBOTS_HOME_PATH)/resources/Makefile.include
