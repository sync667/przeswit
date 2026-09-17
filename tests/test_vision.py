import unittest
from unittest.mock import patch
from przeswit import local_vision as v
class VisionTests(unittest.TestCase):
    def test_block_untrusted_image_hosts(self):
        for url in ['http://127.0.0.1/a.jpg','https://localhost/a.jpg','https://cdn3.park4night.com.evil.test/a.jpg','https://user:pass@cdn3.park4night.com/a.jpg','https://cdn3.park4night.com:444/a.jpg']:
            with self.subTest(url=url),self.assertRaises(ValueError):v.image_bytes(url)
    def test_reject_non_image_payload(self):
        with self.assertRaises(ValueError):v.image_bytes('data:image/png;base64,aGVsbG8=')
    def test_score_validation(self):
        valid=dict(match=50,summary='Widok',visible=['Łąka'],unknown=['Dojazd'],red_flags=[])
        self.assertEqual(v.validate(valid)['match'],50)
        for score in [True,float('nan'),101,-1,'80']:
            with self.subTest(score=score),self.assertRaises(ValueError):v.validate(dict(valid,match=score))
    def test_fingerprint_ignores_review_but_tracks_source(self):
        p=dict(name='Test',photos=[{'url':'one'}]);h=v.fingerprint(p)
        self.assertEqual(h,v.fingerprint(dict(p,local_match={'match':90})))
        self.assertNotEqual(h,v.fingerprint(dict(p,photos=[{'url':'two'}])))
    def test_service_unavailable(self):
        with patch.object(v,'local_call',side_effect=TimeoutError):self.assertFalse(v.status()['ready'])
