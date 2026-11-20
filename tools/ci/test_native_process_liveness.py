"""Pure /proc parser regression: descendants, orphans, process isolation."""
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from native_process_liveness import snapshot

def create_process(proc, pid, ppid, pgrp, *, name='controller worker'):
    directory = proc / str(pid)
    directory.mkdir()
    fields = ['S', str(ppid), str(pgrp)] + ['0'] * 8 + ['12', '4'] + ['0'] * 8 + ['99']
    assert len(fields) == 22
    (directory / 'stat').write_text(f'{pid} ({name}) ' + ' '.join(fields) + '\n')
    (directory / 'wchan').write_text('futex_wait_queue')

class TestNativeProcessLiveness(unittest.TestCase):
    def test_process_family_and_orphaned_group(self):
        with TemporaryDirectory() as folder:
            proc = Path(folder)
            create_process(proc, 100, 1, 100, name='timeout')
            create_process(proc, 101, 100, 101, name='webots (child)')
            create_process(proc, 102, 101, 102, name='crazyflie')
            create_process(proc, 103, 1, 100, name='orphan')
            create_process(proc, 104, 1, 104, name='unrelated')
            result = snapshot(100, proc)
            self.assertTrue(result['root_seen'])
            self.assertEqual([p['pid'] for p in result['processes']], [100, 101, 102, 103])
            self.assertEqual(result['processes'][1]['comm'], 'webots (child)')
            self.assertEqual(result['processes'][1]['user_ticks'], 12)
            self.assertEqual(result['processes'][1]['rss_pages'], 99)
    def test_missing_root_never_becomes_pass(self):
        with TemporaryDirectory() as folder:
            value = snapshot(777, Path(folder))
            self.assertEqual(value['processes'], [])
            self.assertFalse(value['root_seen'])

if __name__ == '__main__':
    unittest.main()
