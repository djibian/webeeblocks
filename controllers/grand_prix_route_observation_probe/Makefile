CXX_SOURCES = grand_prix_route_observation_probe.cpp ../grand_prix_u_flight/grand_prix_u_deadline.cpp
CFLAGS = -std=c++17 -DWEBEEBLOCKS_GP_ROUTE_MODE -I../grand_prix_u_flight
USE_C_API = true
null :=
space := $(null) $(null)
WEBOTS_HOME_PATH ?= $(subst $(space),\ ,$(strip $(subst \,/,$(WEBOTS_HOME))))
include $(WEBOTS_HOME_PATH)/resources/Makefile.include
