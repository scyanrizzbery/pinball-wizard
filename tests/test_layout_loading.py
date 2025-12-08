import unittest
import json
import os
import sys
# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from pbwizard.vision import SimulatedFrameCapture

class TestDynamicLayout(unittest.TestCase):
    def test_load_layout(self):
        sim = SimulatedFrameCapture()
        
        # Define a custom layout
        custom_layout = {
            "flippers": {
                "left": { "x_min": 0.1, "x_max": 0.3, "y_min": 0.7, "y_max": 0.8 },
                "right": { "x_min": 0.7, "x_max": 0.9, "y_min": 0.7, "y_max": 0.8 }
            },
            "bumpers": [
                { "x": 0.2, "y": 0.2, "radius_ratio": 0.1, "value": 500 }
            ],
            "drop_targets": [],
            "guide_lines": { "y": 0.5 }
        }
        
        # Load the layout
        success = sim.load_layout(custom_layout)
        self.assertTrue(success)
        
        # Verify changes
        self.assertEqual(sim.layout.left_flipper_x_min, 0.1)
        self.assertEqual(sim.layout.right_flipper_x_max, 0.9)
        
        # Verify bumper loaded (via layout)
        self.assertGreater(len(sim.layout.bumpers), 0)
        self.assertEqual(sim.layout.bumpers[0]['value'], 500)
        
        self.assertEqual(len(sim.layout.drop_targets), 0)
        
        print("Dynamic layout loading verified successfully!")

if __name__ == '__main__':
    unittest.main()
