"""Fast, explicit, bounded tests of the presentation-only mmap protocol."""
import mmap
import os
import tempfile
import unittest
from types import SimpleNamespace

from tools.ci.experiments.pose_mailbox_v1 import PoseWriter, SIZE, read_once, U64


class PoseMailboxTests(unittest.TestCase):
    def setUp(self):
        self.t = tempfile.TemporaryDirectory()
        self.addCleanup(self.t.cleanup)
        self.p = os.path.join(self.t.name, 'latest.bin')
        fd = os.open(self.p, os.O_CREAT | os.O_EXCL | os.O_RDWR, 0o600)
        os.ftruncate(fd, SIZE)
        os.close(fd)

    def test_overwrite_preserves_latest_only_and_changes_incarnation(self):
        w = PoseWriter(self.p)
        fd = os.open(self.p, os.O_RDONLY)
        reader = mmap.mmap(fd, SIZE, access=mmap.ACCESS_READ)
        os.close(fd)
        self.addCleanup(reader.close)
        self.assertIsNone(read_once(reader))
        pose = SimpleNamespace(kinematics=SimpleNamespace(
            position=(0., 0., .4),
            orientation=(1., 0., 0., 0., 1., 0., 0., 0., 1.),
            time_ms=8))
        first = SimpleNamespace(attempt=1, epoch='private-A')
        second = SimpleNamespace(attempt=2, epoch='private-B')
        w.publish(first, pose)
        old = read_once(reader)
        self.assertTrue(old['valid'])
        self.assertEqual(old['sequence'], 1)
        self.assertNotIn('private-A', repr(old))
        for index in range(2, 1002):
            pose.kinematics.time_ms = index*8
            w.publish(first,pose)
        self.assertEqual(read_once(reader)['sequence'], 1001)
        self.assertEqual(len(reader), SIZE)
        w.publish(second,pose)
        latest=read_once(reader)
        self.assertNotEqual(old['incarnation'], latest['incarnation'])
        self.assertEqual(latest['sequence'], 1002)
        self.assertEqual(w.summary()['epoch_changes'], 2)
        self.assertEqual(w.summary()['publications'], 1002)
        w.close()

    def test_torn_guard_rejected_and_tombstone_revokes_pose(self):
        w=PoseWriter(self.p)
        fd=os.open(self.p,os.O_RDWR)
        reader=mmap.mmap(fd,SIZE,access=mmap.ACCESS_WRITE)
        os.close(fd)
        self.addCleanup(reader.close)
        w.publish(SimpleNamespace(attempt=1,epoch=1),None)
        self.assertFalse(read_once(reader)['valid'])
        U64.pack_into(reader,0,3)
        self.assertIsNone(read_once(reader))
        U64.pack_into(reader,0,2)
        U64.pack_into(reader,SIZE-8,4)
        self.assertIsNone(read_once(reader))
        w.close()


if __name__ == '__main__':
    unittest.main()
