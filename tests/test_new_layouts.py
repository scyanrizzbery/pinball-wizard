import unittest
import json
import os
from pbwizard.vision import SimulatedFrameCapture

class TestNewLayouts(unittest.TestCase):
    def test_load_all_layouts(self):
        sim = SimulatedFrameCapture()
        layouts_dir = os.path.join(os.getcwd(), 'layouts')
        # Update list to match actual creative layouts
        layout_files = ['the_maze.json', 'pachinko_style.json']
        
        for filename in layout_files:
            filepath = os.path.join(layouts_dir, filename)
            print(f"Testing layout: {filename}")
            
            with open(filepath, 'r') as f:
                config = json.load(f)
            
            success = sim.load_layout(config)
            self.assertTrue(success, f"Failed to load {filename}")
            
            # Specific verification for each layout
            if filename == 'the_maze.json':
                # The Maze should have many rails (walls)
                # Note: rails in layout might be merged or processed, but count should be high
                self.assertGreater(len(sim.layout.rails), 10)
            elif filename == 'pachinko_style.json':
                # Pachinko should have many bumpers (pins)
                self.assertGreater(len(sim.bumpers), 10)
                # And minimal/no rails
                self.assertLess(len(sim.layout.rails), 5)

        print("All new layouts verified successfully!")

if __name__ == '__main__':
    unittest.main()
