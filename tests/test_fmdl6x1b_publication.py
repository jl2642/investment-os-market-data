import importlib.util
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("publication", ROOT / "scripts" / "validate_fmdl6x1b_publication.py")
publication = importlib.util.module_from_spec(spec)
spec.loader.exec_module(publication)


class TestFMDL6X1BPublication(unittest.TestCase):
    def test_publication_passes(self):
        self.assertEqual(publication.validate(), [])


if __name__ == "__main__":
    unittest.main()
