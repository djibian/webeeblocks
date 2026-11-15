# CI-only range witness: never link into the product/physical flight binary.
C_SOURCES = progression_decision_h_range_probe.c
null :=
space := $(null) $(null)
WEBOTS_HOME_PATH?=$(subst $(space),\ ,$(strip $(subst \,/,$(WEBOTS_HOME))))
include $(WEBOTS_HOME_PATH)/resources/Makefile.include
