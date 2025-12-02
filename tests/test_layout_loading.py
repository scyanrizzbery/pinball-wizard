import unittest
import json
import os
from pbwizard.vision import SimulatedFrameCapture

class TestDynamicLayout(unittest.TestCase):
    def test_load_layout(self):
        sim = SimulatedFrameCapture(headless=True)
        
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
        self.assertEqual(len(sim.bumpers), 1)
        self.assertEqual(sim.bumpers[0]['value'], 500)
        self.assertEqual(len(sim.drop_target_states), 0)
        
        print("Dynamic layout loading verified successfully!")

if __name__ == '__main__':
    unittest.main()
