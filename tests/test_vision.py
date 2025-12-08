import unittest
import numpy as np
from unittest.mock import MagicMock, patch
from pbwizard.vision import SimulatedFrameCapture, ZoneManager

class TestVision(unittest.TestCase):

    def test_zone_manager(self):
        zm = ZoneManager(200, 200)
        
        # Test Left Zone
        status = zm.get_zone_status(50, 100)
        self.assertTrue(status['left'])
        self.assertFalse(status['right'])
        
        # Test Right Zone
        status = zm.get_zone_status(150, 100)
        self.assertFalse(status['left'])
        self.assertTrue(status['right'])
        
        # Test Center (managed by logic)
        status = zm.get_zone_status(100, 100)
        # Assuming >= width/2 is right
        self.assertFalse(status['left'])
        self.assertTrue(status['right'])

    def test_simulated_frame_capture_init(self):
        sim = SimulatedFrameCapture(width=600, height=800)
        self.assertEqual(sim.width, 600)
        self.assertEqual(sim.height, 800)
        self.assertIsNotNone(sim.physics_engine)

    def test_update_physics_params(self):
        sim = SimulatedFrameCapture(width=600, height=800)
        
        # Mock physics engine to verify calls
        sim.physics_engine = MagicMock()
        sim.physics_engine.config = MagicMock()
        
        params = {'gravity_magnitude': 2000.0, 'flipper_length': 120.0}
        sim.update_physics_params(params)
        
        # Verify params updated in local storage
        self.assertEqual(sim.layout.physics_params['gravity_magnitude'], 2000.0)
        
        # Verify calls to physics engine
        # config is a Mock object, so update call is recorded on it
        sim.physics_engine.config.update.assert_called_with(params)
        sim.physics_engine.apply_config_changes.assert_called()

    def test_create_rail(self):
        sim = SimulatedFrameCapture(width=600, height=800)
        # Mock physics engine
        sim.physics_engine = MagicMock()
        sim.physics_engine.layout = MagicMock()
        
        rail_data = {'p1': {'x': 0.1, 'y': 0.1}, 'p2': {'x': 0.2, 'y': 0.2}}
        sim.create_rail(rail_data)
        
        self.assertIn(rail_data, sim.layout.rails)
        self.assertTrue(sim.physics_engine._rebuild_rails.called)

    def test_create_bumper(self):
        sim = SimulatedFrameCapture(width=600, height=800)
        sim.physics_engine = MagicMock()
        sim.physics_engine.layout = MagicMock()
        
        bumper_data = {'x': 0.5, 'y': 0.5, 'radius_ratio': 0.05}
        sim.create_bumper(bumper_data)
        
        self.assertIn(bumper_data, sim.layout.bumpers)
        sim.physics_engine.update_bumpers.assert_called_with(sim.layout.bumpers)

if __name__ == "__main__":
    unittest.main()
