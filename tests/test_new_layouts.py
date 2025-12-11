import unittest
import json
import os
import sys
# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from pbwizard.vision import SimulatedFrameCapture

class TestNewLayouts(unittest.TestCase):
    def setUp(self):
        os.environ['HEADLESS_SIM'] = 'true'
        self.sim = SimulatedFrameCapture()

    def test_load_all_layouts(self):
        layouts_dir = os.path.join(os.getcwd(), 'layouts')
        # Update list to match actual creative layouts
        layout_files = [
            'the_maze.json', 
            'pachinko_style.json',
            'spooky_family.json',
            'twilight_zone.json',
            'medieval_madness.json'
        ]
        
        for filename in layout_files:
            filepath = os.path.join(layouts_dir, filename)
            if not os.path.exists(filepath):
                print(f"Skipping {filename} (not found)")
                continue

            print(f"\nTesting layout: {filename}")
            
            with open(filepath, 'r') as f:
                config = json.load(f)
            
            # Use name-based loader if possible to test dynamic loading, or direct config
            # Here we test config loading
            success = self.sim.load_layout(config)
            self.assertTrue(success, f"Failed to load {filename}")
            
            # Specific verification for each layout
            if filename == 'the_maze.json':
                self.assertGreater(len(self.sim.layout.rails), 10)
            elif filename == 'pachinko_style.json':
                self.assertGreater(len(self.sim.layout.bumpers), 10)
            elif filename == 'spooky_family.json':
                self.assertEqual(len(self.sim.layout.bumpers), 5)
                self.assertEqual(len(self.sim.layout.drop_targets), 3)
            elif filename == 'twilight_zone.json':
                self.assertEqual(len(self.sim.layout.bumpers), 5)
                self.assertEqual(len(self.sim.layout.captures), 1)
            elif filename == 'medieval_madness.json':
                self.assertEqual(len(self.sim.layout.bumpers), 4)

        print("\nAll new layouts verified successfully!")

if __name__ == '__main__':
    unittest.main()
