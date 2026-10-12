#!/usr/bin/env python3
"""Compile the real simulation observer with transport/clock injection."""
from pathlib import Path
import subprocess
import tempfile
ROOT=Path(__file__).resolve().parents[2]
HEADER=r'''
#pragma once
#ifdef __cplusplus
extern "C" {
#endif
typedef void *WbNodeRef;
typedef void *WbFieldRef;
double wb_robot_get_time(void);
void wb_robot_wwi_send_text(const char *);
WbNodeRef wb_supervisor_node_get_from_def(const char *);
WbNodeRef wb_supervisor_node_get_self(void);
WbFieldRef wb_supervisor_node_get_field(WbNodeRef,const char *);
void wb_supervisor_field_set_sf_string(WbFieldRef,const char *);
const char *wb_supervisor_field_get_sf_string(WbFieldRef);
#ifdef __cplusplus
}
#endif
'''
PROBE=r'''
#include <cassert>
#include <cstring>
#include <deque>
#include <iostream>
#include <string>
#include <vector>
#include <webots/robot.h>
extern "C" const char *webeeblocks_gp_receive_text(void);
extern "C" void webeeblocks_gp_send(const char *,int);
std::deque<std::string> incoming;
std::string current,control,channel="WEBEEBLOCKS_ACTIVITY_ATTEMPT_V1 1";
std::vector<std::string> sent;
double now=2;
int selfToken=0,evaluatorToken=0,controlToken=0,channelToken=0;
extern "C" double wb_robot_get_time(void){return now;}
extern "C" void wb_robot_wwi_send_text(const char *s){sent.push_back(s);}
extern "C" void *wb_supervisor_node_get_from_def(const char *s){return !std::strcmp(s,"GP_EVALUATOR")?&evaluatorToken:nullptr;}
extern "C" void *wb_supervisor_node_get_self(void){return &selfToken;}
extern "C" void *wb_supervisor_node_get_field(void *n,const char *s){return !std::strcmp(s,"customData")?(n==&selfToken?&channelToken:&controlToken):nullptr;}
extern "C" void wb_supervisor_field_set_sf_string(void *f,const char *s){(f==&controlToken?control:channel)=s;}
extern "C" const char *wb_supervisor_field_get_sf_string(void *f){return (f==&controlToken?control:channel).c_str();}
extern "C" const char *webeeblocks_file_broker_receive_text(void){if(incoming.empty())return nullptr;current=incoming.front();incoming.pop_front();return current.c_str();}
extern "C" void webeeblocks_file_broker_send(const char *s,int){sent.push_back(s);if(std::string(s)=="WEBEEBLOCKS_RUNTIME_V2 RESPONSE 8 OK")channel="WEBEEBLOCKS_ACTIVITY_ATTEMPT_V1 2";}
void response(const std::string &s){webeeblocks_gp_send(s.c_str(),s.size()+1);}
void request(const std::string &s){incoming.push_back(s);}
int main(){
 request("WEBEEBLOCKS_RUNTIME_V2 REQUEST 1 GP_MODE 1");
 assert(webeeblocks_gp_receive_text()==nullptr);assert(sent.back()=="WEBEEBLOCKS_RUNTIME_V2 RESPONSE 1 OK");
 request("WEBEEBLOCKS_RUNTIME_V2 REQUEST 2 TAKEOFF 0.9");
 assert(std::string(webeeblocks_gp_receive_text()).find("TAKEOFF")!=std::string::npos);
 assert(control=="GP_START attempt=1 time=2.000000000 debug=1 state=pending");
 now=3;response("WEBEEBLOCKS_RUNTIME_V2 RESPONSE 2 OK");
 assert(control=="GP_START attempt=1 time=2.000000000 debug=1 state=accepted");
 request("WEBEEBLOCKS_RUNTIME_V2 REQUEST 20 VERTICAL down 0.5");
 assert(std::string(webeeblocks_gp_receive_text()).find("VERTICAL")!=std::string::npos);response("WEBEEBLOCKS_RUNTIME_V2 RESPONSE 20 OK");
 request("WEBEEBLOCKS_RUNTIME_V2 REQUEST 21 VERTICAL up 0.5");
 assert(std::string(webeeblocks_gp_receive_text()).find("VERTICAL")!=std::string::npos);response("WEBEEBLOCKS_RUNTIME_V2 RESPONSE 21 OK");
 request("WEBEEBLOCKS_RUNTIME_V2 REQUEST 22 VERTICAL up 0.3");assert(webeeblocks_gp_receive_text()==nullptr);
 assert(sent.back()=="WEBEEBLOCKS_RUNTIME_V2 RESPONSE 22 ERR INVALID_VERTICAL");
 request("WEBEEBLOCKS_RUNTIME_V2 REQUEST 3 STOP");webeeblocks_gp_receive_text();
 assert(control.find("state=failed")!=std::string::npos);
 response("WEBEEBLOCKS_RUNTIME_V2 RESPONSE 2 OK");
 assert(control.find("state=failed")!=std::string::npos);
 request("WEBEEBLOCKS_RUNTIME_V2 REQUEST 4 GP_MODE 0");assert(webeeblocks_gp_receive_text()==nullptr);
 assert(control.find("debug=1")!=std::string::npos);
 request("WEBEEBLOCKS_RUNTIME_V2 REQUEST 5 TAKEOFF 0.9");webeeblocks_gp_receive_text();response("WEBEEBLOCKS_RUNTIME_V2 RESPONSE 5 OK");
 assert(control.find("time=2.000000000")!=std::string::npos);
 now=603;assert(std::string(webeeblocks_gp_receive_text())=="WEBEEBLOCKS_RUNTIME_V2 REQUEST 2147483647 STOP");
 assert(webeeblocks_gp_receive_text()==nullptr);assert(webeeblocks_gp_receive_text()==nullptr);
 request("WEBEEBLOCKS_RUNTIME_V2 REQUEST 7 RESET");webeeblocks_gp_receive_text();response("WEBEEBLOCKS_RUNTIME_V2 RESPONSE 7 ERR RESET_TIMEOUT");
 assert(control.find("state=failed")!=std::string::npos);
 request("WEBEEBLOCKS_RUNTIME_V2 REQUEST 8 RESET");webeeblocks_gp_receive_text();response("WEBEEBLOCKS_RUNTIME_V2 RESPONSE 8 OK");
 assert(control.empty());
 request("WEBEEBLOCKS_RUNTIME_V2 REQUEST 9 TAKEOFF 0.9");webeeblocks_gp_receive_text();
 assert(control=="GP_START attempt=2 time=603.000000000 debug=0 state=pending");
 response("WEBEEBLOCKS_RUNTIME_V2 RESPONSE 2 OK");assert(control.find("state=pending")!=std::string::npos);
 response("WEBEEBLOCKS_RUNTIME_V2 RESPONSE 9 OK");assert(control.find("state=accepted")!=std::string::npos);
 response("WEBEEBLOCKS_RUNTIME_V2 RESPONSE 10 ERR INVALID_RANGE_SAMPLE");assert(control.find("state=failed")!=std::string::npos);
 std::cout<<"PASS Grand Prix observer: accepted timestamp, terminal veto, late ACK, one-shot deadline, exact successful Reset, stale reply and invalid sample\n";
}
'''
def main():
    with tempfile.TemporaryDirectory() as temp:
        root=Path(temp)
        for file in ['webots/robot.h','webots/supervisor.h','webots/plugins/robot_window/default.h']:
            path=root/file;path.parent.mkdir(parents=True,exist_ok=True);path.write_text(HEADER)
        probe=root/'probe.cpp';probe.write_text(PROBE)
        subprocess.run(['g++','-std=c++17','-Wall','-Wextra','-I',str(root),str(ROOT/'controllers/grand_prix_flight/grand_prix_bridge.cpp'),str(probe),'-o',str(root/'probe')],check=True)
        subprocess.run([str(root/'probe')],check=True)
if __name__=='__main__':main()
