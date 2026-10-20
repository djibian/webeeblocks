"""One known-binary Chrome155 control; not historical browser reconstruction."""
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
LATEST='https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb'
PINNED='https://dl.google.com/linux/chrome/deb/pool/main/g/google-chrome-stable/google-chrome-stable_155.0.8059.84-1_amd64.deb'
DEB='8fbd2ae69cdf7ee98b7513c3396a7b5e06f974f8625fdd590df3091dd0c3e9de'
EXE='cb19b59995072b86cc7f887b3b1c7ab1f63518a7f2ed9f0d33249e1a040e2c76'
def pin(command):
    if command.count(LATEST)!=1:raise ValueError('ambiguous original URL')
    install='DEBIAN_FRONTEND=noninteractive apt-get install -y /tmp/google-chrome.deb >/dev/null'
    if command.count(install)!=1:raise ValueError('ambiguous installation')
    return command.replace(LATEST,PINNED).replace(install,
      "echo '"+DEB+"  /tmp/google-chrome.deb' | sha256sum -c -\n"+install+"\n"+
      "echo '"+EXE+"  /opt/google/chrome/chrome' | sha256sum -c -")
def main():
    spec=importlib.util.spec_from_file_location('physics_base',HERE/'run.py')
    base=importlib.util.module_from_spec(spec);spec.loader.exec_module(base)
    original_run=subprocess.run
    out=base.runner.ARTIFACT_ROOT
    def selected_run(*args,**kwargs):
        arguments=list(args);command=arguments[0] if arguments else kwargs.get('args')
        if isinstance(command,list) and command and command[0]=='docker' and LATEST in command[-1]:
            before=command[-1];after=pin(before)
            (out/'pinned-command-original.sh').write_text(before)
            (out/'pinned-command-executed.sh').write_text(after)
            command=[*command[:-1],after]
            if arguments:arguments[0]=command
            else:kwargs['args']=command
        return original_run(*arguments,**kwargs)
    subprocess.run=selected_run
    result=1
    try:result=base.main()
    finally:
        subprocess.run=original_run
        if out.exists():
            (out/'pinned-browser-run.py').write_bytes(Path(__file__).read_bytes())
            (out/'PIN155_PROTOCOL.md').write_bytes((HERE/'PIN155_PROTOCOL.md').read_bytes())
            (out/'pinned-browser.json').write_text(json.dumps({'url':PINNED,'deb_sha256':DEB,'executable_sha256':EXE,'planned':1,'replacement':False,'result':result,'scope':'known earlier control binary, historical browser unknown'},indent=2)+'\n')
            (out/'sha256.json').write_text(json.dumps({p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in out.iterdir() if p.is_file() and p.name!='sha256.json'},indent=2)+'\n')
    return result
if __name__=='__main__':
    if sys.argv[1:]==['self-test']:
        text='set -e\nwget -q -O /tmp/google-chrome.deb '+LATEST+'\nDEBIAN_FRONTEND=noninteractive apt-get install -y /tmp/google-chrome.deb >/dev/null\n'
        changed=pin(text);assert LATEST not in changed and DEB in changed and EXE in changed
        subprocess.run(['bash','-n'],input=changed,text=True,check=True)
        for bad in ('',text+text):
            try:pin(bad)
            except ValueError:pass
            else:raise AssertionError('ambiguous selection accepted')
        print('PIN155 transform self-test PASS')
    else:raise SystemExit(main())
