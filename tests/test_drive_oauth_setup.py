import importlib.util
import os
from pathlib import Path
import tempfile
import tomllib
from types import SimpleNamespace
import unittest

spec = importlib.util.spec_from_file_location('setup_drive_oauth', Path(__file__).resolve().parents[1] / 'tools/setup_drive_oauth.py')
setup = importlib.util.module_from_spec(spec)
spec.loader.exec_module(setup)


class OAuthSetupTests(unittest.TestCase):
    def test_exclusive_private_toml_output(self):
        credentials = SimpleNamespace(client_id='test-client', client_secret='test-"secret', refresh_token='test-refresh')
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'secrets.toml'
            setup.write_secrets(path, credentials)
            parsed = tomllib.loads(path.read_text())
            self.assertEqual(parsed['drive_oauth']['client_secret'], credentials.client_secret)
            if os.name == 'posix':
                self.assertEqual(path.stat().st_mode & 0o777, 0o600)
            with self.assertRaises(FileExistsError):
                setup.write_secrets(path, credentials)
            self.assertEqual(tomllib.loads(path.read_text()), parsed)

    def test_no_output_without_refresh_token(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'secrets.toml'
            with self.assertRaises(ValueError):
                setup.write_secrets(path, SimpleNamespace(refresh_token=None))
            self.assertFalse(path.exists())


if __name__ == '__main__':
    unittest.main()
