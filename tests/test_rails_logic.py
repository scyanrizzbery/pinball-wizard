import unittest
from unittest.mock import MagicMock
import sys
import os

# Add src to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from pbwizard.vision import SimulatedFrameCapture

class TestRailsLogic(unittest.TestCase):
    def setUp(self):
        # Mock layout and physics engine
        self.mock_layout = MagicMock()
        self.mock_layout.rails = []
        
        self.mock_physics = MagicMock()
        
        self.capture = SimulatedFrameCapture(width=100, height=100)
        self.capture.layout = self.mock_layout
        self.capture.physics_engine = self.mock_physics
        
    def test_create_rail(self):
        rail_data = {'p1': {'x': 0.1, 'y': 0.1}, 'p2': {'x': 0.2, 'y': 0.2}}
        self.capture.create_rail(rail_data)
        
        self.assertEqual(len(self.capture.layout.rails), 1)
        self.assertEqual(self.capture.layout.rails[0], rail_data)
        self.mock_physics._rebuild_rails.assert_called_once()
        
    def test_update_rails(self):
        # Setup initial rails
        self.capture.layout.rails = [{'p1': {'x': 0, 'y': 0}, 'p2': {'x': 1, 'y': 1}}]
        
        new_rails = [{'p1': {'x': 0.5, 'y': 0.5}, 'p2': {'x': 0.6, 'y': 0.6}}]
        self.capture.update_rails(new_rails)
        
        self.assertEqual(self.capture.layout.rails, new_rails)
        self.mock_physics._rebuild_rails.assert_called()
        
    def test_delete_rail(self):
        # Setup initial rails
        self.capture.layout.rails = [
            {'id': 1},
            {'id': 2}
        ]
        
        self.capture.delete_rail(0)
        
        self.assertEqual(len(self.capture.layout.rails), 1)
        self.assertEqual(self.capture.layout.rails[0]['id'], 2)
        self.mock_physics._rebuild_rails.assert_called()

if __name__ == "__main__":
    unittest.main()
