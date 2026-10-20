"""Offline byte verification and reanalysis of the retained native acquisitions."""
import hashlib
import importlib.util
import json
from pathlib import Path
import tarfile
from analyze import summarize
from instrument import instrument
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
spec=importlib.util.spec_from_file_location('contact_run',ROOT/'experiments/runtime-reset-contact/run.py')
contact=importlib.util.module_from_spec(spec);spec.loader.exec_module(contact)
if __name__=='__main__':
    results=json.loads((HERE/'RESULTS.json').read_text())
    for mode,expected in results['experiments'].items():
        archive=HERE/expected['archive']
        assert hashlib.sha256(archive.read_bytes()).hexdigest()==expected['archive_sha256']
        with tarfile.open(archive) as tar:
            files={str(Path(member.name).relative_to(mode)):tar.extractfile(member).read()
                   for member in tar.getmembers() if member.isfile()}
        for manifest_name in ('sha256.json','acquisition-sha256.json'):
            manifest=json.loads(files[manifest_name])
            assert all(hashlib.sha256(files[name]).hexdigest()==digest for name,digest in manifest.items())
        assert instrument(files['runtime-original.c'].decode()).encode()==files['runtime-instrumented.c']
        # The C source named by original provenance is the actual instrumented input.
        provenance=json.loads(files['provenance.json'])
        assert provenance['git_head']==results['main']
        c_digests=[v for k,v in provenance['sha256'].items() if k.endswith('/crazyflie_runtime_v2.c')]
        assert c_digests==[hashlib.sha256(files['runtime-instrumented.c']).hexdigest()]
        assert summarize(files['controller-0.log'].decode())==json.loads(files['phase-summary.json'])
        assert summarize(files['controller-0.log'].decode())['resets'][-1]==expected['attempt7_reset']
        rows=[json.loads(line) for line in files['events.jsonl'].splitlines()]
        native=''.join(files[f'controller-{i}.log'].decode() for i in range(8))
        assert contact.validate_events('baseline',rows,native)['reset_acknowledgements']==7
        assert len(files['native-reset-state.jsonl'].splitlines())-1==expected['native_samples']
        print(mode, 'verified;', expected['native_samples'], 'native samples; seven strict RESETs; no RESET_TIMEOUT reproduction')
