import unittest
from unittest.mock import MagicMock
import sys
import os
import numpy as np

# Add src to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from pbwizard.vision import SimulatedFrameCapture, PinballLayout
from pbwizard.physics import PymunkEngine

class TestNewRailAlignment(unittest.TestCase):
    def setUp(self):
        # Setup layout with default offsets (simulating legacy layout)
        config = {
            'width': 1.0,
            'height': 2.0,
            'rails': [],
            'rail_x_offset': -0.61,
            'rail_y_offset': -0.11
        }
        self.layout = PinballLayout(config=config)
        
        # Verify offsets are PERSISTED (not baked)
        self.assertEqual(self.layout.rail_x_offset, -0.61)
        self.assertEqual(self.layout.rail_y_offset, -0.11)
        
        # Setup Physics Engine
        self.physics = PymunkEngine(self.layout, 100, 200) # 100x200 pixels
        self.physics.rail_x_offset = 0.0
        self.physics.rail_y_offset = 0.0
        
        # Setup Capture
        self.capture = SimulatedFrameCapture(width=100, height=200)
        self.capture.layout = self.layout
        self.capture.physics_engine = self.physics
        
    def test_new_rail_alignment(self):
        # Create a new rail at specific coordinates
        # Default coords from frontend are typically 0.4, 0.4 to 0.6, 0.6
        new_rail = {
            'p1': {'x': 0.4, 'y': 0.4},
            'p2': {'x': 0.6, 'y': 0.6}
        }
        
        # Action: Create Rail
        self.capture.create_rail(new_rail)
        
        # Verify Layout State
        self.assertEqual(len(self.layout.rails), 1)
        self.assertEqual(self.layout.rails[0]['p1']['x'], 0.4)
        self.assertEqual(self.layout.rails[0]['p1']['y'], 0.4)
        
        # Verify Physics State
        # Physics engine should have created a body/shape for this rail.
        # We need to check the coordinates of the created shape.
        # PymunkEngine stores static lines in self.space.static_body usually, or separate bodies?
        # Let's check how _rebuild_rails works. It adds shapes to self.space.
        
        # Accessing private shapes might be tricky, let's inspect self.rail_shapes if it exists
        # or iterate space.shapes.
        
        rail_shapes = [s for s in self.physics.space.shapes if hasattr(s, 'collision_type') and s.collision_type == 8] # 8 is rail
        
        # Find the shape that matches our expected rail
        found_match = False
        matching_shape = None
        
        for shape in rail_shapes:
            bb = shape.bb
            # Check if BB roughly matches expected coordinates (allowing for thickness)
            # Expected P1: (40, 80), P2: (60, 120)
            # BB should cover x range [40, 60] and y range [80, 120]
            # With thickness, it will be slightly larger.
            
            # Simple check: does it contain the center point?
            mid_x = 50.0
            mid_y = 100.0
            
            if bb.left <= mid_x <= bb.right and bb.bottom <= mid_y <= bb.top:
                found_match = True
                matching_shape = shape
                break
        
        self.assertTrue(found_match, f"No matching rail shape found. Shapes: {[s.bb for s in rail_shapes]}")
        
        # Verify bounds of the matching shape
        bb = matching_shape.bb
        print(f"Matched Rail BB: {bb}")
        
        # Verify that NO offset was applied (should be positive coordinates)
        self.assertGreater(bb.left, 0)

if __name__ == "__main__":
    unittest.main()
