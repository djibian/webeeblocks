#!/usr/bin/env python3
"""Reproduce #665's pefile 8192-export false refusals on the exact build ZIP.

Static table completeness only: Win32 loading and ABI execution stay separate.
Requires pefile==2024.8.26. Does not install or alter a DLL.
"""
import argparse
import hashlib
import json
from pathlib import Path
import zipfile

ARCHIVE_SHA256 = '86b9540cd5a41bdd5680fb81f00d35befb6610da26f414fffb67123e7267301e'
QT_DLLS = ('Qt6Core.dll', 'Qt6Gui.dll', 'Qt6Widgets.dll')


def diagnose(archive):
    import pefile
    if pefile.__version__ != '2024.8.26':
        raise ValueError('The historical pefile version is required')
    if hashlib.sha256(archive.read_bytes()).hexdigest() != ARCHIVE_SHA256:
        raise ValueError('Wrong original Windows build archive')
    with zipfile.ZipFile(archive) as z:
        if z.testzip() is not None or len(z.namelist()) != len(set(z.namelist())):
            raise ValueError('Invalid or duplicated archive entries')
        pe_bytes = z.read('webots-bin.exe')
        if hashlib.sha256(pe_bytes).hexdigest() != z.read('pe.sha256').decode().split()[0]:
            raise ValueError('Build manifest does not identify the PE')
        exe = pefile.PE(data=pe_bytes, fast_load=True)
        exe.parse_data_directories(directories=[pefile.DIRECTORY_ENTRY['IMAGE_DIRECTORY_ENTRY_IMPORT']])
        needed = {d.dll.decode(): [s.name for s in d.imports] for d in exe.DIRECTORY_ENTRY_IMPORT
                  if d.dll.decode() in QT_DLLS}
        if set(needed) != set(QT_DLLS) or any(None in symbols for symbols in needed.values()):
            raise ValueError('Unexpected Qt import graph or untested ordinal')
        result = {'claim': 'static-export-parser-truncation-only-not-native-ABI-qualification',
                  'build_artifact': 12695533700, 'archive_sha256': ARCHIVE_SHA256, 'dlls': {}}
        for name in QT_DLLS:
            data = z.read(name)
            row = {'sha256': hashlib.sha256(data).hexdigest(), 'imports': len(needed[name]), 'scans': []}
            for cap in (8192, 65536):
                pe = pefile.PE(data=data, fast_load=True, max_symbol_exports=cap)
                pe.parse_data_directories(directories=[pefile.DIRECTORY_ENTRY['IMAGE_DIRECTORY_ENTRY_EXPORT']])
                table = pe.DIRECTORY_ENTRY_EXPORT
                names = {s.name for s in table.symbols if s.name is not None}
                absent = [s.decode() for s in needed[name] if s not in names]
                row['scans'].append({'cap': cap, 'declared_names': table.struct.NumberOfNames,
                    'parsed_unique_names': len(names), 'missing_imports': absent, 'warnings': pe.get_warnings()})
                if cap == 65536 and (len(names) != table.struct.NumberOfNames or absent or pe.get_warnings()):
                    raise ValueError(f'Full static name table incomplete or imports unresolved: {name}')
                pe.close()
            result['dlls'][name] = row
        exe.close()
        if [len(result['dlls'][name]['scans'][0]['missing_imports']) for name in QT_DLLS] != [0, 11, 6]:
            raise ValueError('Historical false refusal was not reproduced exactly')
        return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--build-archive', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    result = diagnose(args.build_archive)
    args.output.write_text(json.dumps(result, indent=2) + '\n')
    print('QT665_PEFILE_TRUNCATION_REPRODUCED=PASS_STATIC_ONLY default_false_missing=17 full_missing=0')
