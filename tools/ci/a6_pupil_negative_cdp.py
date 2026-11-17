"""Draft-only A6: a non-solving Blockly flight and RESET through real student buttons.

Uses the actual Webots R2025a school Robot Window and CDP mouse input.
Never submits a scoring solution and never substitutes native ACK/mission evidence.
Not an OS Save/Open or Windows acceptance test.
"""
from __future__ import annotations
import hashlib
import re
import time


def _browser_state(dev):
    return dev.eval("""(() => {
      const element = id => document.getElementById(id);
      const run = element('submit');
      const reset = element('resetSimulation');
      const manager = window.WebeeBlocksProjectManager;
      return {
        status: element('runtimeState').textContent.trim(),
        profile: runtimeProfile && runtimeProfile.id,
        scene: runtimeProfile && runtimeProfile.runtime.scene,
        native_scene: runtimeBackend && runtimeBackend.sceneIdentity,
        running: runtimeRunning === true,
        terminal: runtimeTerminal === true,
        pending: runtimeOutcomePending === true,
        run_available: !!run && !run.hidden && !run.disabled,
        reset_available: !!reset && !reset.hidden && !reset.disabled,
        project: manager && manager.encodeCurrent(),
        workspace: JSON.stringify(Blockly.serialization.workspaces.save(workspace))
      };
    })()""")


def _click_real_button(dev, button_id):
    # CDP mouse, NOT element.click(), hidden DOM handler or runtime API.
    point = dev.eval("""(function(id) {
      const b=document.getElementById(id);
      if (!b || b.disabled || b.hidden) return null;
      const r=b.getBoundingClientRect();
      return r.width>5 && r.height>5 ?
        {x:r.left+r.width/2,y:r.top+r.height/2}:null;
    })(""" + repr(button_id) + ")")
    if not point:
        raise AssertionError("A6 visible student button unavailable: " + button_id)
    args={"x":point["x"],"y":point["y"],"button":"left","clickCount":1}
    dev.call("Input.dispatchMouseEvent",{"type":"mousePressed",**args})
    dev.call("Input.dispatchMouseEvent",{"type":"mouseReleased",**args})


_ACK = re.compile(r"(?m)^WEBEEBLOCKS_RUNTIME_V2 RESPONSE ([0-9]+) SCENE_OK ([0-9a-f]{64})$")
_READY = re.compile(r"(?m)^WEBEEBLOCKS_A6_MOTOR_READY n=1 ")
_REJECT = re.compile(r"(?m)^WEBEEBLOCKS_A6_MOTOR_REJECT attempt=([1-9][0-9]*) behavioral_oracle=1$")


def negative_flight_then_reset(dev, process, log, read_text, fatal_markers):
    """Proof is about the *actual* UI controls, not a solution for counting H."""
    state = _browser_state(dev)
    before = dev.state()
    if (state["profile"]!="progression-count-h-v1" or
        state["scene"]!="count-h-1-v1" or
        state["native_scene"]!="count-h-1-v1" or
        state["status"]!="PRÊT" or state["terminal"] or state["pending"] or
        not state["run_available"]):
        raise AssertionError("A6 negative-pupil attempt not Ready in actual UI")
    if not state["project"] or state["project"]!=before["project"]:
        raise AssertionError("A6 actual browser manager unavailable before flight")
    baseline = read_text(log)
    ack_before = _ACK.findall(baseline)
    ready_before = len(_READY.findall(baseline))
    if _REJECT.search(baseline):
        raise AssertionError("stale A6 native rejected attempt before student flight")
    if len(ack_before)!=4 or len({n for _,n in ack_before})!=4 or ready_before!=2:
        raise AssertionError("A/B/C/A native epochs absent before pupil run")
    program_bytes=state["project"]
    workspace_bytes=state["workspace"]

    # Already installed from the REAL Blockly APIs in the earlier scene test:
    # takeoff(0.4), speed(0.2), land; intentionally cannot pass A6.
    _click_real_button(dev,"submit")
    outcome=None
    until=time.monotonic()+140
    while time.monotonic()<until:
        trace=read_text(log)
        if any(s in trace for s in fatal_markers) or process.poll() is not None:
            raise AssertionError("A6 native fatal/exit during real Blockly negative flight")
        state=_browser_state(dev)
        if state["status"] in ("ERREUR","ARRÊTÉ","À CORRIGER"):
            raise AssertionError("A6 native flight failed instead of judging mission: "+str(state))
        if state["terminal"] and not state["running"] and not state["pending"]:
            # Native A6 oracle reports MOTOR_REJECT, not a fictional
            # RESPONSE STATE not-achieved packet. Require the one *new*
            # first-attempt reject after clicking the actual Run button.
            rejects=_REJECT.findall(trace)
            if (state["status"]!="MISSION NON RÉUSSIE" or
                not state["reset_available"] or rejects!=["1"]):
                raise AssertionError("A6 missing fresh native MOTOR_REJECT or RESET: "+str(state))
            if (state["workspace"]!=workspace_bytes or
                state["project"]!=program_bytes):
                raise AssertionError("negative native flight altered nonempty Blockly")
            outcome=state["status"]
            break
        time.sleep(0.35)
    if outcome is None:
        raise AssertionError("real A6 student negative flight did not reach native verdict")

    # Student presses the actual visible RESET control; the backend must
    # revoke the old scene epoch and import a *new* trusted native scene.
    _click_real_button(dev,"resetSimulation")
    after=None
    until=time.monotonic()+75
    while time.monotonic()<until:
        trace=read_text(log)
        if any(s in trace for s in fatal_markers) or process.poll() is not None:
            raise AssertionError("A6 native fatal/exit during real student RESET")
        state=_browser_state(dev)
        acks=_ACK.findall(trace)
        ready_count=len(_READY.findall(trace))
        if (state["status"]=="PRÊT" and not state["terminal"] and
            not state["running"] and not state["pending"] and
            state["run_available"] and
            state["scene"]=="count-h-1-v1" and
            state["native_scene"]=="count-h-1-v1" and
            state["workspace"]==workspace_bytes and
            state["project"]==program_bytes and
            len(acks)==5 and ready_count==ready_before+1 and
            len({nonce for _,nonce in acks})==5):
            after=state
            break
        time.sleep(0.35)
    if after is None:
        raise AssertionError("A6 student RESET did not restore a fresh native A world and same Blockly")
    print("A6_REAL_PUPIL_NEGATIVE_RESET_PASS native_failure=true "
          "fresh_scene_after_reset=true same_nonempty_wbb=true "
          "os_save_open=UNPROVEN", flush=True)
    return {"native_outcome":outcome,
            "scene_ack_count":5,
            "n1_native_observer_incarnations":ready_before+1,
            "workspace_sha256":hashlib.sha256(workspace_bytes.encode()).hexdigest(),
            "wbb_sha256":hashlib.sha256(program_bytes.encode()).hexdigest(),
            "scope":"actual Chrome mouse -> Blockly -> native failure -> fresh RESET"}
