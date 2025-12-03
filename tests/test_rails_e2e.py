import unittest
from unittest.mock import MagicMock
import sys
import os

# Add src to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from pbwizard import web_server

class TestRailsE2E(unittest.TestCase):
    def setUp(self):
        web_server.app.config['TESTING'] = True
        self.client = web_server.socketio.test_client(web_server.app)
        self.mock_vision = MagicMock()
        # Mock the capture object inside vision_system
        self.mock_vision.capture = MagicMock()
        web_server.vision_system = self.mock_vision
        
    def test_update_rails(self):
        rails_data = [{'p1': {'x': 0, 'y': 0}, 'p2': {'x': 1, 'y': 1}}]
        self.client.emit('update_rails', rails_data, namespace='/config')
        
        # Check if vision_system.update_rails was called
        # web_server checks vision_system.update_rails OR vision_system.capture.update_rails
        # We'll assume it tries vision_system first
        # But in the code:
        # if hasattr(vision_system, 'update_rails'): ...
        # elif hasattr(vision_system.capture, 'update_rails'): ...
        
        # Since MagicMock has all attributes, it should hit the first one.
        self.mock_vision.update_rails.assert_called_with(rails_data)
        
    def test_create_rail(self):
        # New event
        rail_data = {'p1': {'x': 0.2, 'y': 0.2}, 'p2': {'x': 0.3, 'y': 0.3}}
        self.client.emit('create_rail', rail_data, namespace='/config')
        
        # Should call create_rail on vision system
        self.mock_vision.create_rail.assert_called_with(rail_data)
        
    def test_delete_rail(self):
        # New event
        rail_index = 1
        self.client.emit('delete_rail', {'index': rail_index}, namespace='/config')
        
        # Should call delete_rail on vision system
        self.mock_vision.delete_rail.assert_called_with(rail_index)

if __name__ == "__main__":
    unittest.main()
