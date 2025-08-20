from io import StringIO
from unittest import TestCase

from config import Config


class TestConfig(TestCase):
    def test_load_file_example(self):
        with open("config.example.txt", "r") as example:
            cfg = Config.load_file(example)
            self.assertEqual(cfg.host, "www.example.com")
            self.assertEqual(cfg.image_path, "data.bin")
            self.assertEqual(cfg.port, 80)
            self.assertEqual(cfg.metadata_path, "metadata.json")
            self.assertEqual(cfg.upload_path, "upload.php")
            self.assertDictEqual(cfg.wifi, {"MySSID": "ssshItsSecret"})

    def test_load_file_string_io(self):
        pretend = """Host: www.example.com
WiFi: MySSID
Pass: ssshItsSecret
WiFi: Another
Pass: different_secret
Image: data.bin
Meta: metadata.json
Up: upload.php
"""
        with StringIO(pretend) as sio:
            cfg = Config.load_file(sio)
            self.assertEqual(cfg.host, "www.example.com")
            self.assertEqual(cfg.image_path, "data.bin")
            self.assertEqual(cfg.port, 80)
            self.assertEqual(cfg.metadata_path, "metadata.json")
            self.assertEqual(cfg.upload_path, "upload.php")
            self.assertDictEqual(
                cfg.wifi, {"MySSID": "ssshItsSecret", "Another": "different_secret"}
            )
