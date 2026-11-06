# Test-only WWI input/ACK wrapper; production C, broker, PID and guard unchanged.
GP_DEADLINE_SOURCE = ../grand_prix_u_flight/grand_prix_u_deadline.cpp grand_prix_route_publisher_probe.cpp
GP_PREPARE_SCRIPT = ../../tools/ci/prepare_grand_prix_route_publisher_probe.py
GP_EXTRA_CFLAGS = -DWEBEEBLOCKS_GP_ROUTE_MODE -I../grand_prix_u_flight
LDFLAGS += -Wl,--wrap=wb_robot_wwi_receive_text -Wl,--wrap=gp_u_send
include ../grand_prix_u_flight/Makefile
