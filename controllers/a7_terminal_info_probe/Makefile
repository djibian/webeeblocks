# A7 PRIVATE terminal observability probe only; never linked to pupil or physical runtime.
C_SOURCES = a7_terminal_info_probe.c
null :=
space := $(null) $(null)
WEBOTS_HOME_PATH?=$(subst $(space),\ ,$(strip $(subst \,/,$(WEBOTS_HOME))))
include $(WEBOTS_HOME_PATH)/resources/Makefile.include
