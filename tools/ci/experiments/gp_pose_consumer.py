"""Presentation-only subprocess, deliberately never connected to Webots APIs."""
import argparse
import json
import mmap
import os
import signal
import time
from tools.ci.experiments.pose_mailbox_v1 import SIZE, read_once


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('path')
    parser.add_argument('out')
    parser.add_argument('--mode', choices=('fast', 'stall'), required=True)
    args = parser.parse_args()
    def stop(*unused):
        raise KeyboardInterrupt
    signal.signal(signal.SIGTERM, stop)
    fd = os.open(args.path, os.O_RDONLY)
    try:
        region = mmap.mmap(fd, SIZE, access=mmap.ACCESS_READ)
    finally:
        os.close(fd)
    last = 0
    samples = 0
    try:
        with open(args.out, 'w') as stream:
            while True:
                item = read_once(region)
                if item is not None and item['sequence'] > last:
                    last = item['sequence']
                    samples += 1
                    stream.write(json.dumps(item, sort_keys=True) + '\n')
                    stream.flush()
                if args.mode == 'stall' and samples >= 3:
                    # The reader truly stops reading forever. The Webots
                    # controller has no handle to this reader and never waits.
                    time.sleep(3600)
                time.sleep(.005 if args.mode == 'fast' else .100)
    except KeyboardInterrupt:
        pass
    finally:
        region.close()
        print(json.dumps(dict(consumer_mode=args.mode, last=last,
                              samples=samples)), flush=True)


if __name__ == '__main__':
    main()
