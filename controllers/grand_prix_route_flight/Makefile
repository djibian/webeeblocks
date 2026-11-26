# Same Runtime, broker, Qt support and LAND/RESET composition, isolated output.
# Only Windows route mode needs the OS-backed 128-bit epoch producer.
ifeq ($(OS),Windows_NT)
GP_DEADLINE_SOURCE = build/grand_prix_route_deadline.cpp
DYNAMIC_LIBRARIES += -lbcrypt
else
GP_DEADLINE_SOURCE = ../grand_prix_u_flight/grand_prix_u_deadline.cpp
endif
GP_PREPARE_SCRIPT = ../../tools/grand_prix/prepare_route_runtime.py
GP_PREPARE_DEPENDENCIES = ../../tools/grand_prix/route_multirate.py \
                         ../../tools/grand_prix/route_multirate_reference.py \
                         ../../tools/grand_prix/route_windows_epoch.py \
                         ../grand_prix_u_flight/grand_prix_u_deadline.cpp
GP_EXTRA_CFLAGS = -DWEBEEBLOCKS_GP_ROUTE_MODE -I../grand_prix_u_flight
include ../grand_prix_u_flight/Makefile
