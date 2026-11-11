"""Diagnostic, non-authoritative single-slot pose mailbox.

One Webots evaluator process may publish a pose into a fixed 160-byte mmap.
Readers never acknowledge, block or send commands to the publisher. Interleaved
readers may see torn data: the version guards and CRC refuse it. No physical
observations, mission commands or oracle fields pass through this mailbox.
"""
import math
from collections import deque
import mmap
import os
import struct
import time
import uuid
import zlib

MAGIC = b'GPPOSE01'
BODY = struct.Struct('<8s16sQQ3d9dI')
SIZE = 8 + BODY.size + 4 + 8
U64 = struct.Struct('<Q')
U32 = struct.Struct('<I')


class PoseWriter:
    def __init__(self, path):
        fd = os.open(path, os.O_RDWR)
        try:
            if os.fstat(fd).st_size != SIZE:
                raise ValueError('not a bounded pose mailbox')
            self.m = mmap.mmap(fd, SIZE, access=mmap.ACCESS_WRITE)
        finally:
            os.close(fd)
        # Pre-fault the single mapped page before the first simulation tick.
        self.m[:] = bytes(SIZE)
        self.incarnation = uuid.uuid4().bytes
        self.current_key = None
        self.sequence = 0
        self.latencies = deque(maxlen=4096)
        self.total_publications = 0
        self.epochs = 0
        self.valid_count = 0

    def publish(self, context, observation):
        now = time.perf_counter_ns()
        # The evaluator's private epoch is NEVER copied to the presentation
        # channel. A random presentation-only incarnation changes on RESET.
        key = None if context is None else (context.attempt, context.epoch)
        if key != self.current_key:
            self.current_key = key
            self.incarnation = uuid.uuid4().bytes
            self.epochs += 1
        valid = observation is not None and key is not None
        if valid:
            kinematics = observation.kinematics
            xyz = tuple(kinematics.position)
            orientation = tuple(kinematics.orientation)
            sim_ms = kinematics.time_ms
            if (len(xyz) != 3 or len(orientation) != 9 or
                    any(not math.isfinite(float(v))
                        for v in xyz + orientation)):
                raise ValueError('invalid native presentation pose')
        else:
            xyz = (0., 0., 0.)
            orientation = (0.,) * 9
            sim_ms = 0
        self.sequence += 1
        seq = self.sequence
        # No locks, flush, queue, reader lookup or OS I/O on this hot path.
        U64.pack_into(self.m, 0, seq * 2 - 1)
        BODY.pack_into(self.m, 8, MAGIC, self.incarnation, seq, sim_ms,
                       *xyz, *orientation, int(valid))
        checksum = zlib.crc32(self.m[8:8 + BODY.size])
        U32.pack_into(self.m, 8 + BODY.size, checksum)
        U64.pack_into(self.m, SIZE - 8, seq * 2)
        U64.pack_into(self.m, 0, seq * 2)
        self.latencies.append(time.perf_counter_ns() - now)
        self.total_publications += 1
        if valid:
            self.valid_count += 1

    def summary(self):
        latencies = sorted(self.latencies)
        return dict(publications=self.total_publications,
                    latency_sample_count=len(latencies),
                    valid=self.valid_count, epoch_changes=self.epochs,
                    max_ns=max(latencies, default=0),
                    mean_ns=(sum(latencies) / len(latencies) if latencies else None),
                    p99_ns=(latencies[min(len(latencies)-1,
                             (len(latencies)*99 + 99)//100 - 1)]
                            if latencies else None),
                    bounded_bytes=SIZE)

    def close(self):
        self.m.close()


def read_once(region):
    if len(region) != SIZE:
        raise ValueError('invalid presentation slot')
    first = U64.unpack_from(region, 0)[0]
    if not first or first % 2:
        return None
    last = U64.unpack_from(region, SIZE - 8)[0]
    data = bytes(region[8:8 + BODY.size])
    checksum = U32.unpack_from(region, 8 + BODY.size)[0]
    if first != last or first != U64.unpack_from(region, 0)[0]:
        return None
    if zlib.crc32(data) != checksum:
        return None
    magic, incarnation, seq, sim_ms, *rest = BODY.unpack(data)
    if magic != MAGIC or seq * 2 != first:
        return None
    return dict(incarnation=uuid.UUID(bytes=incarnation).hex,
                sequence=seq, time_ms=sim_ms, position=rest[:3],
                orientation=rest[3:12], valid=bool(rest[12]))
