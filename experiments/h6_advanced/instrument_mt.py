#!/usr/bin/env python3
"""Observability-only MT topology check after canonical native R/G patch."""
from pathlib import Path
import sys
if len(sys.argv)!=2: raise SystemExit("usage: instrument_mt.py PATCHED_WEBOTS_SOURCE")
root=Path(sys.argv[1]);p=root/"src/webots/engine/WbSimulationCluster.cpp"
s=p.read_text()
a="void WbSimulationCluster::step() {"
if s.count(a)!=1: raise SystemExit("REFUSED no unique cluster step")
s=s.replace(a,'''void WbSimulationCluster::step() {
  // Experimental trace only: ODE configuration actually selected in Webots.
  static bool h6ThreadReported = false;
  if (!h6ThreadReported && std::getenv("H6_NATIVE_TRACE")) {
    std::fprintf(stderr, "H6_NATIVE_THREAD_COUNT configured=%d\\n",
                 mContext->numberOfThreads());
    std::fflush(stderr);
    h6ThreadReported = true;
  }''')
if s.count("#include <cassert>") != 1: raise SystemExit("REFUSED C++ includes")
s=s.replace("#include <cassert>","#include <cassert>\n#include <cstdio>\n#include <cstdlib>")
p.write_text(s)
print("H6_NATIVE_MT_TRACE_INSTALLED")
