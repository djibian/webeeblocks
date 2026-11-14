# CI-only native observer. Not linked to the pupil/runtime/physical binary.
C_SOURCES = progression_count_h_flight_observer.c
CFLAGS = -I../progression_count_h_v1
null :=
space := $(null) $(null)
WEBOTS_HOME_PATH?=$(subst $(space),\ ,$(strip $(subst \,/,$(WEBOTS_HOME))))
include $(WEBOTS_HOME_PATH)/resources/Makefile.include
