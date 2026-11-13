# Native scene-local orientation evaluator, never linked into the qualified
# physical flight controller or the student Blockly runtime.
C_SOURCES = progression_orientation_3d.c
null :=
space := $(null) $(null)
WEBOTS_HOME_PATH?=$(subst $(space),\ ,$(strip $(subst \,/,$(WEBOTS_HOME))))
include $(WEBOTS_HOME_PATH)/resources/Makefile.include
