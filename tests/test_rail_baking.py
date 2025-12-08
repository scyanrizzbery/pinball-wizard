import unittest
import sys
import os

# Add src to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from pbwizard.vision import PinballLayout

class TestRailBaking(unittest.TestCase):
    def test_offset_baking(self):
        config = {
            'rails': [
                {'p1': {'x': 0.1, 'y': 0.1}, 'p2': {'x': 0.2, 'y': 0.2}}
            ],
            'rail_x_offset': 0.5,
            'rail_y_offset': 0.5
        }
        
        layout = PinballLayout(config=config)
        
        # Check if offsets are PERSISTED (not baked)
        # Rails should remain as defined
        self.assertAlmostEqual(layout.rails[0]['p1']['x'], 0.1)
        self.assertAlmostEqual(layout.rails[0]['p1']['y'], 0.1)
        self.assertAlmostEqual(layout.rails[0]['p2']['x'], 0.2)
        self.assertAlmostEqual(layout.rails[0]['p2']['y'], 0.2)
        
        # Offsets should be stored
        self.assertEqual(layout.rail_x_offset, 0.5)
        self.assertEqual(layout.rail_y_offset, 0.5)

if __name__ == "__main__":
    unittest.main()
