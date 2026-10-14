.DEFAULT_GOAL := release
C_SOURCES = build/runtime.c ../crazyflie_square/pid_controller.c
CXX_SOURCES = ../../tools/ci/fixtures/gp_u_pose_driver.cpp build/broker.cpp build/deadline.cpp
CFLAGS = -DGP_NATIVE -I../crazyflie_square -I../crazyflie_runtime_v2 -I../grand_prix_u_flight -include ../grand_prix_u_flight/grand_prix_u_hook.h
USE_C_API = true
include $(WEBOTS_HOME)/resources/Makefile.include
