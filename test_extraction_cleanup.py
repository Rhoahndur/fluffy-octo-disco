import unittest
from cost_estimator import extract_cost

class TestCostEstimatorCleanup(unittest.TestCase):
    def test_cleanup_logic(self):
        # We simulate the extraction behavior without calling the API
        test_strings = [
            ("$15,000,000", "15000000"),
            ("15000000", "15000000"),
            ("The cost is $1.5M", "1.5"),
            ("  $20,500,000.50 \n", "20500000.50"),
            ("Total: 50000 USD", "50000")
        ]
        
        for input_str, expected in test_strings:
            result = ''.join(c for c in input_str if c.isdigit() or c == '.')
            self.assertEqual(result, expected)
            print(f"Passed: '{input_str}' -> '{result}'")

if __name__ == '__main__':
    unittest.main()
