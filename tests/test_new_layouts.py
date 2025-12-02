import unittest
import json
import os
from pbwizard.vision import SimulatedFrameCapture

class TestNewLayouts(unittest.TestCase):
    def test_load_all_layouts(self):
        sim = SimulatedFrameCapture(headless=True)
        layouts_dir = os.path.join(os.getcwd(), 'layouts')
        layout_files = ['bumper_forest.json', 'precision.json', 'wide_open.json']
        
        for filename in layout_files:
            filepath = os.path.join(layouts_dir, filename)
            print(f"Testing layout: {filename}")
            
            with open(filepath, 'r') as f:
                config = json.load(f)
            
            success = sim.load_layout(config)
            self.assertTrue(success, f"Failed to load {filename}")
            
            # Basic verification of loaded state
            if filename == 'bumper_forest.json':
                self.assertEqual(len(sim.bumpers), 6)
            elif filename == 'precision.json':
                self.assertEqual(len(sim.bumpers), 1)
                self.assertAlmostEqual(sim.layout.left_flipper_x_max, 0.45)
            elif filename == 'wide_open.json':
                self.assertEqual(len(sim.bumpers), 0)

        print("All new layouts verified successfully!")

if __name__ == '__main__':
    unittest.main()
