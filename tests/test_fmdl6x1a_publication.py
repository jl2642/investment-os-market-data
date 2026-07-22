from __future__ import annotations
import importlib.util
from pathlib import Path
import unittest
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('v',ROOT/'scripts/validate_fmdl6x1a_publication.py')
v=importlib.util.module_from_spec(spec); spec.loader.exec_module(v)
class TestPublication(unittest.TestCase):
    def test_publication(self): self.assertEqual(v.validate(),[])
if __name__=='__main__': unittest.main()
