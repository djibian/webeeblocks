#!/usr/bin/env python3
"""Generate normal Webots real 2-dynamic-body contact fixture; no injected ODE joints."""
from pathlib import Path
import sys
if len(sys.argv)!=2: raise SystemExit("usage: generate_foreign_world.py BASE_WORLD")
p=Path(sys.argv[1])
source=p.read_text()
marker="DEF TARGET Solid {"
if source.count(marker)!=1 or source.count("  optimalThreadCount 1")!=1:
    raise SystemExit("REFUSED noncanonical inherited world")
foreign="""DEF FOREIGN Solid {
  translation 0 0 0.302
  name "foreign"
  children [
    Shape {
      appearance PBRAppearance { baseColor 0.1 0.3 0.8 roughness 1 }
      geometry Box { size 0.2 0.2 0.2 }
    }
  ]
  boundingObject Box { size 0.2 0.2 0.2 }
  physics Physics { mass 0.12 }
}
"""
for n in (1,2):
    w=source.replace(marker,foreign+marker)
    w=w.replace("  optimalThreadCount 1",f"  optimalThreadCount {n}")
    output=p.with_name(f"h6_rg_foreign_threads{n}.wbt")
    output.write_text(w)
    print("H6_FOREIGN_WORLD",output,n)
