"""Non-executable Webots fixture for L and final-closure native probes (#825).

The scene deliberately has NO open H, evaluator, runnable Blockly or mission
admission. It is useful only for independently instrumented L/terminal sensor
and contact experiments. Do not use as the Grand Prix teacher workspace.
"""
from tools.grand_prix.route_v2 import Route
from tools.grand_prix.route_solid_v2 import static_world
from tools.grand_prix.route_terminal_v2 import terminal_boxes


def static_l_terminal_probe_world(route):
    """Preserve the already-specified physical corner and terminal Solids."""
    if not isinstance(route, Route):
        raise TypeError("a variable Route is required")
    scene = static_world(route)
    robot_anchor = "\nCrazyflie {"
    title_anchor = "L-corner STATIC " + route.identifier
    if (scene.count(robot_anchor) != 1 or
            scene.count(title_anchor) != 1 or
            scene.count("DEF GP_V2_L_") != 4 or
            "GP_V2_FINAL_" in scene or
            scene.count('controller "<none>"') != 1 or
            scene.count('window "<none>"') != 1):
        raise RuntimeError("static Webots fixture anchors changed; refusing composition")
    terminal = terminal_boxes(route)
    if (len(terminal) != 4 or
            len({item.name for item in terminal}) != 4 or
            any(not item.vrml().startswith("DEF " + item.name + " Solid {")
                for item in terminal)):
        raise RuntimeError("terminal collider inventory changed")
    # The corridor-only red guide is NOT the final boundary of the widened
    # arrival area. Remove it rather than publish a misleading track outline.
    # Full world/oracle composition must consume course_footprint_v2 separately.
    lines = [line for line in scene.splitlines()
             if not line.startswith("DEF GP_V2_RED_")]
    scene = "\n".join(lines)
    scene = scene.replace(title_anchor,
                          "L+terminal STATIC PROBE (not a mission) " +
                          route.identifier)
    scene = scene.replace(robot_anchor, "\n" +
                          "\n".join(item.vrml() for item in terminal) +
                          robot_anchor, 1)
    if (scene.count("DEF GP_V2_FINAL_") != 4 or
            scene.count("boundingObject Box { size ") != 8 or
            "DEF GP_V2_RED_" in scene or
            'controller "grand_prix_u_flight"' in scene or
            "GP_ROUTE_EVALUATOR" in scene):
        raise RuntimeError("static probe composition incomplete or executable")
    return scene
