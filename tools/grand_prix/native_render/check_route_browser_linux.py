"""Run the real route-5 Robot Window and pilot on Linux with visible Webots.

A failing mission is diagnostic evidence. The user-facing Windows checkpoint
requires the installed project and browser on the target hardware.
"""
import argparse
import base64
from contextlib import ExitStack
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time
from urllib.parse import quote
from urllib.request import urlopen

from websockets.sync.client import connect

PROGRAM = '''(function () {
  const ws = Blockly.getMainWorkspace();
  if (ws.getAllBlocks(false).length) throw new Error('expected an empty workspace');
  function make(type, id) {
    const b = ws.newBlock(type, id);
    b.initSvg(); b.render(); return b;
  }
  function number(id, value) {
    const b = make('math_number', id); b.setFieldValue(String(value), 'NUM'); return b;
  }
  const takeoff = make('webeeblocks_v2_takeoff', 'bench-takeoff');
  takeoff.getInput('HEIGHT').connection.connect(number('bench-height', 0.4).outputConnection);
  const move = make('webeeblocks_v2_move', 'bench-move');
  move.setFieldValue('forward', 'DIRECTION');
  move.getInput('DISTANCE').connection.connect(number('bench-distance', 1.0).outputConnection);
  const land = make('webeeblocks_v2_land', 'bench-land');
  takeoff.nextConnection.connect(move.previousConnection);
  move.nextConnection.connect(land.previousConnection);
  return Blockly.serialization.workspaces.save(ws);
})()'''


def await_value(fn, name, timeout=35):
    limit = time.monotonic() + timeout
    while time.monotonic() < limit:
        value = fn()
        if value:
            return value
        time.sleep(.12)
    raise RuntimeError('timeout: ' + name)


def start(stack, folder, name, command, env):
    log = stack.enter_context((folder / (name + '.log')).open('wb'))
    child = subprocess.Popen(command, stdout=log, stderr=log, cwd=folder, env=env)

    def retire():
        if child.poll() is None:
            child.terminate()
            try:
                child.wait(timeout=4)
            except subprocess.TimeoutExpired:
                child.kill()
                child.wait()
    stack.callback(retire)
    return child


def browser_target(port):
    try:
        with urlopen(f'http://127.0.0.1:{port}/json/list', timeout=1) as body:
            pages = json.load(body)
        return next((p['webSocketDebuggerUrl'] for p in pages if p['type'] == 'page'), None)
    except OSError:
        return None


class Page:
    def __init__(self, connection):
        self.connection = connection
        self.sequence = 0

    def call(self, method, **params):
        self.sequence += 1
        self.connection.send(json.dumps(dict(id=self.sequence, method=method, params=params)))
        while True:
            response = json.loads(self.connection.recv(timeout=8))
            if response.get('id') == self.sequence:
                if 'error' in response:
                    raise RuntimeError(str(response))
                return response['result']

    def evaluate(self, js):
        reply = self.call('Runtime.evaluate', expression=js, returnByValue=True)
        if 'exceptionDetails' in reply:
            raise RuntimeError(str(reply))
        return reply['result'].get('value')


def trial(project, home, browser, folder, scale, duty, port, debug_port):
    from tools.grand_prix.launch_linux import configure_render_fps, render_route
    from tools.grand_prix.route_courses_v2 import reference_course

    course = reference_course(5)
    folder.mkdir(parents=True)
    (folder / 'worlds').mkdir()
    (folder / 'plugins').symlink_to(project / 'plugins', target_is_directory=True)
    # Webots finds the world-adjacent project plugins directory.
    world = folder / 'worlds/route.wbt'
    scene = configure_render_fps(render_route(course), 60)
    for name in ('grand_prix_route_flight', 'grand_prix_route_evaluator'):
        assert scene.count('controller "'+name+'"') == 1
        scene = scene.replace('controller "'+name+'"', 'controller "<extern>"')
    world.write_text(scene, encoding='utf-8')
    env = {k:v for k,v in os.environ.items() if k.lower() not in ('http_proxy','https_proxy','all_proxy')}
    env.update(WEBOTS_HOME=str(home), WEBOTS_EXPERIMENT_MAIN_RENDER_SCALE=str(scale), WEBOTS_RENDER_TRACE='1',
               WEBEEBLOCKS_GP_STEP_WALL_PROBE='1', WEBOTS_DISABLE_SAVE_SCREEN_PERSPECTIVE_ON_CLOSE='true',
               WEBOTS_EXPERIMENT_RENDER_DUTY=str(duty), WEEBEE_ROUTE_LAB_PROJECT=str(project))
    controller = [str(home/'webots-controller'),'--protocol=tcp','--ip-address=127.0.0.1',f'--port={port}']
    browser_url = f'http://127.0.0.1:{port}/robot_windows/grand_prix_route_v2/grand_prix_route_v2.html?name='+quote('Crazyflie WebeeBlocks')
    with ExitStack() as stack:
        webots = start(stack, folder, 'webots', [str(home/'webots'),'--batch','--stdout','--stderr','--mode=realtime',
                    '--extern-urls',f'--port={port}',f'--log-performance={folder / "performance.log"},0',str(world)],env)
        def waiting():
            if webots.poll() is not None:
                raise RuntimeError('engine failed during startup')
            return (folder/'webots.log').read_text(errors='replace').count('Waiting for local or remote connection') >= 2
        await_value(waiting,'Webots TCP supervisor and pilot')
        start(stack, folder, 'pilot', [*controller,'--robot-name=Crazyflie WebeeBlocks',
              str(project/'controllers/grand_prix_route_flight/grand_prix_route_flight'),course.identifier],env)
        start(stack, folder, 'evaluator', [*controller,'--robot-name=Évaluateur Grand Prix variable',
              str(Path(__file__).resolve()),course.identifier],env)
        start(stack, folder, 'browser', [str(browser),'--no-sandbox','--disable-dev-shm-usage',
              '--disable-background-networking','--disable-gpu','--remote-debugging-address=127.0.0.1',
              f'--remote-debugging-port={debug_port}','--window-size=980,700',f'--user-data-dir={folder/"chrome"}',
              browser_url],env)
        endpoint=await_value(lambda:browser_target(debug_port),'Chromium CDP')
        page=Page(stack.enter_context(connect(endpoint, proxy=None)))
        await_value(lambda:page.evaluate('typeof Blockly==="object" && Blockly.getMainWorkspace()?.rendered'), 'real Blockly')
        workspace = page.evaluate(PROGRAM)
        (folder/'workspace.json').write_text(json.dumps(workspace, sort_keys=True, indent=2) + '\n')
        project_data = {
            'format': 'webeeblocks-project', 'version': 1,
            'activity': {
                'id': 'progression-grand-prix-route-v2',
                'semantics': page.evaluate('WebeeBlocksSemanticAst.compileWorkspace(Blockly.getMainWorkspace()).semantics'),
            },
            'workspace': workspace,
        }
        (folder/'diagnostic.wbb').write_text(
            json.dumps(project_data, sort_keys=True, indent=2) + '\n', encoding='utf-8')
        status='document.body.dataset.runtimeState'
        await_value(lambda:page.evaluate(status+'==="PRÊT" && !document.getElementById("submit").disabled'), 'native READY',75)
        print(folder.name,'READY',flush=True)
        page.evaluate('document.getElementById("submit").click()')
        await_value(lambda:page.evaluate(status+'!=="PRÊT"'), 'Blockly launch')
        states=[]
        def outcome():
            value=page.evaluate(status)
            if value not in states:
                states.append(value)
            return value if value in ('MISSION ÉCHOUÉE','TERMINÉ','SUCCÈS','ERREUR','REFUSÉ') else None
        result=await_value(outcome,'Blockly outcome',130)
        detail=page.evaluate('document.getElementById("runtimeDetail").textContent')
        debug=page.evaluate('document.getElementById("debugState").textContent')
        png=page.call('Page.captureScreenshot',format='png')['data']
        (folder/'blockly.png').write_bytes(base64.b64decode(png))
        (folder/'result.json').write_text(json.dumps(dict(outcome=result, states=states, detail=detail, debug=debug,
             world_sha256=hashlib.sha256(world.read_bytes()).hexdigest(), scale=scale, render_duty=duty),indent=2)+'\n')
        print(folder.name, result, detail, flush=True)



def run_evaluator():
    # Only the TCP fixture changes the two controller names to <extern>.
    # Preserve all other native scene and safety checks in the evaluator.
    import runpy
    from controller import Node

    root = Path(os.environ['WEEBEE_ROUTE_LAB_PROJECT'])
    get_field = Node.getField


    def external_fixture(node, name):
        field = get_field(node, name)
        if name == 'controller' and field is not None:
            expected = None
            if node.getTypeName() == 'Crazyflie' and get_field(node, 'name').getSFString() == 'Crazyflie WebeeBlocks':
                expected = 'grand_prix_route_flight'
            elif node.getDef() == 'GP_ROUTE_EVALUATOR':
                expected = 'grand_prix_route_evaluator'
            if expected and field.getSFString() == '<extern>':
                field.getSFString = lambda: expected
        return field


    Node.getField = external_fixture
    runpy.run_path(str(root / 'controllers/grand_prix_route_evaluator/grand_prix_route_evaluator.py'), run_name='__main__')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('project', 'engine', 'browser', 'output'):
        parser.add_argument('--' + name, type=lambda path: Path(path).resolve(), required=True)
    parser.add_argument('--trials', nargs='+', default=['100:0', '50:0'], metavar='SCALE:DUTY')
    parser.add_argument('--port', type=int, default=1376)
    parser.add_argument('--debug-port', type=int, default=9228)
    args = parser.parse_args()
    trials = [tuple(map(int, item.split(':'))) for item in args.trials]
    if any(scale not in (50, 100) or not 0 <= duty < 100 for scale, duty in trials):
        parser.error('expected scale 50 or 100 and duty 0..99')
    if (args.engine / 'resources/version.txt').read_text().strip() != 'R2025a':
        parser.error('expected an R2025a distribution')
    args.output.mkdir()
    inputs = {
        'project_sha': subprocess.check_output(
            ['git', '-C', str(args.project), 'rev-parse', 'HEAD'], text=True).strip(),
        'engine': {},
    }
    for relative in ('bin/webots-bin', 'lib/controller/libController.so'):
        with (args.engine / relative).open('rb') as stream:
            inputs['engine'][relative] = hashlib.file_digest(stream, 'sha256').hexdigest()
    (args.output/'inputs.json').write_text(json.dumps(inputs, indent=2) + '\n', encoding='utf-8')
    sys.path.insert(0, str(args.project))
    for i, (scale, duty) in enumerate(trials):
        trial(args.project, args.engine, args.browser, args.output / f'{i+1}-{scale}-{duty}',
              scale, duty, args.port + i, args.debug_port + i)


if __name__ == '__main__':
    if 'WEEBEE_ROUTE_LAB_PROJECT' in os.environ:
        run_evaluator()
    else:
        main()
