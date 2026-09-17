import unittest,tempfile,json,sqlite3
from pathlib import Path
from unittest.mock import patch
from concurrent.futures import ThreadPoolExecutor
from app import storage as s,profiles as p,ai_runtime as runtime
class ParallelDatabaseTests(unittest.TestCase):
    def test_atomic_claims_and_backup(self):
        with tempfile.TemporaryDirectory() as folder,patch.object(s,'DATA',Path(folder)):
            s.init();p.init();s.upsert([dict(source='test',id=str(i),name='Spot '+str(i)) for i in range(12)]);p.sync_queue()
            with ThreadPoolExecutor(max_workers=4) as pool:rows=list(pool.map(lambda _:p.claim_next(),range(12)))
            self.assertEqual(len({r['key'] for r in rows}),12)
            self.assertIsNone(p.claim_next())
            s.save_note('test:1','shortlist','Keep me')
            backup=s.daily_backup();self.assertEqual(backup,s.daily_backup())
            db=sqlite3.connect(backup)
            try:
                self.assertEqual(db.execute('pragma integrity_check').fetchone()[0],'ok')
                self.assertEqual(db.execute('select count(*) from places').fetchone()[0],12)
                self.assertEqual(db.execute('select note from notes').fetchone()[0],'Keep me')
            finally:db.close()
    def test_admission_preserves_resource_margin(self):
        self.assertEqual(runtime.admission('auto',dict(gpu_total_mb=23028,gpu_free_mb=9000,ram_free_mb=50000)),2)
        self.assertEqual(runtime.admission('auto',dict(gpu_total_mb=23028,gpu_free_mb=2200,ram_free_mb=50000)),1)
        self.assertEqual(runtime.admission('auto',dict(gpu_total_mb=23028,gpu_free_mb=1000,ram_free_mb=50000)),0)
        self.assertEqual(runtime.admission('auto',dict(gpu_total_mb=23028,gpu_free_mb=9000,ram_free_mb=2000)),0)
        self.assertEqual(runtime.admission('1',dict(gpu_total_mb=23028,gpu_free_mb=9000,ram_free_mb=50000)),1)
        self.assertEqual(runtime.admission('auto',{}),1)
