"""Integrity and resume checks for the optional HTTP downloader, without network."""
import hashlib
import io
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from evolv_openlm.download import download_snapshot


class Response(io.BytesIO):
    def __init__(self, data, status=200, headers=None):
        super().__init__(data)
        self.status = status
        self.headers = headers or {}


class DownloadTests(unittest.TestCase):
    def fixture(self, data=b"official weights"):
        revision = "a" * 40
        meta = SimpleNamespace(rfilename="model.safetensors", size=len(data),
                               lfs=SimpleNamespace(sha256=hashlib.sha256(data).hexdigest()))
        return revision, SimpleNamespace(sha=revision, siblings=[meta])

    def test_verified_file_is_reused_offline(self):
        revision, info = self.fixture()
        with tempfile.TemporaryDirectory() as folder, patch("huggingface_hub.HfApi") as api:
            api.return_value.model_info.return_value = info
            with patch("urllib.request.urlopen", return_value=Response(b"official weights")) as fetch:
                root = download_snapshot("Qwen/example", revision, folder)
                self.assertEqual((root / "model.safetensors").read_bytes(), b"official weights")
                download_snapshot("Qwen/example", revision, folder)
                self.assertEqual(fetch.call_count, 1)

    def test_wrong_hash_does_not_promote_partial_file(self):
        revision, info = self.fixture()
        with tempfile.TemporaryDirectory() as folder, patch("huggingface_hub.HfApi") as api:
            api.return_value.model_info.return_value = info
            with patch("urllib.request.urlopen", return_value=Response(b"corrupt! weights")):
                with self.assertRaisesRegex(RuntimeError, "hash"):
                    download_snapshot("Qwen/example", revision, folder)
            root = Path(folder) / "models--Qwen--example/snapshots" / revision
            self.assertFalse((root / "model.safetensors").exists())

    def test_resume_requires_matching_content_range(self):
        revision, info = self.fixture()
        with tempfile.TemporaryDirectory() as folder, patch("huggingface_hub.HfApi") as api:
            api.return_value.model_info.return_value = info
            root = Path(folder) / "models--Qwen--example/snapshots" / revision
            root.mkdir(parents=True)
            partial = root / "model.safetensors.http-part"
            partial.write_bytes(b"official")
            with patch("urllib.request.urlopen", return_value=Response(b" weights", 206, {"Content-Range": "bytes 0-7/16"})):
                with self.assertRaisesRegex(RuntimeError, "retomada"):
                    download_snapshot("Qwen/example", revision, folder)
            self.assertEqual(partial.read_bytes(), b"official")


if __name__ == "__main__":
    unittest.main()
