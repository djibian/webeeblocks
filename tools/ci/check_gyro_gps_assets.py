#!/usr/bin/env python3
"""Fail closed on an incomplete pinned boxChallenge EXTERNPROTO closure."""
from pathlib import Path
import re
import sys


def check(source):
    source = Path(source).resolve()
    repo = Path(__file__).resolve().parents[2]
    remote = 'https://raw.githubusercontent.com/cyberbotics/webots/R2025a/'
    visited = set()

    def visit(path):
        path = path.resolve()
        if not path.is_relative_to(source) or not path.is_file():
            raise ValueError(f'missing or escaping pinned asset: {path}')
        if path in visited:
            return
        visited.add(path)
        for url in re.findall(r'EXTERNPROTO\s+"([^"]+)"', path.read_text()):
            target = source / url[len('webots://'):] if url.startswith('webots://') else path.parent / url
            if '://' in url and not url.startswith('webots://'):
                raise ValueError(f'unpinned nested EXTERNPROTO: {url}')
            visit(target)

    urls = re.findall(r'EXTERNPROTO\s+"([^"]+)"', (repo/'worlds/boxChallenge.wbt').read_text())
    if len(urls) != 5 or any(not url.startswith(remote) for url in urls):
        raise ValueError('boxChallenge pinned roots changed')
    for url in urls:
        visit(source / url[len(remote):])
    # The same full subtrees preserve dynamically chosen textures and the
    # Pioneer motor sound; this check does not rewrite any PROTO or world.
    for item in ('projects/default/worlds/sounds/rotational_motor.wav',
                 'projects/default/worlds/textures/checkered_parquetry.jpg',
                 'projects/default/worlds/textures/metal.jpg'):
        if not (source/item).is_file():
            raise ValueError(f'missing pinned resource: {item}')
    return len(visited)


if __name__ == '__main__':
    print(f'PASS pinned Gyro/GPS assets: {check(sys.argv[1])} transitive PROTOs and historical resources')
