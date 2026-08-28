import unittest

from strategy_kernel_v2.validate_program_amendment_a1 import validate

class ProgramAmendmentA1Tests(unittest.TestCase):
    def test_amendment_is_frozen_and_consistent(self):
        self.assertEqual(validate(), [])

if __name__ == "__main__":
    unittest.main()
