import unittest
import sys
import os
import time
from dataclasses import dataclass

# Add parent directory to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from pbwizard.vision import SimulatedFrameCapture
from pbwizard.physics import PymunkEngine
from pbwizard.config import PhysicsConfig

class MockLayout:
    def __init__(self):
        self.physics_params = {}
        self.left_flipper_x_min = 0.0
        self.left_flipper_x_max = 0.0
        self.left_flipper_y_min = 0.0
        self.left_flipper_y_max = 0.0
        self.right_flipper_x_min = 0.0
        self.right_flipper_x_max = 0.0
        self.right_flipper_y_min = 0.0
        self.right_flipper_y_max = 0.0

class MockPhysicsEngine:
    def __init__(self):
        self.config = PhysicsConfig()
        self.balls = []
        self.flippers = {}
    
    def apply_config_changes(self):
        pass
    
    def update_rail_params(self, **kwargs):
        # Mocking logic that might update internal state or config
        if 'thickness' in kwargs: self.config.guide_thickness = kwargs['thickness']
        if 'length_scale' in kwargs: self.config.guide_length_scale = kwargs['length_scale']
        if 'angle_offset' in kwargs: self.config.guide_angle_offset = kwargs['angle_offset']
        if 'x_offset' in kwargs: self.config.rail_x_offset = kwargs['x_offset']
        if 'y_offset' in kwargs: self.config.rail_y_offset = kwargs['y_offset']
    
    def update_flipper_length(self, length):
        self.config.flipper_length = float(length)

class TestPhysicsParamsUpdate(unittest.TestCase):
    def setUp(self):
        self.capture = SimulatedFrameCapture(width=800, height=600)
        self.capture.layout = MockLayout()
        self.capture.physics_engine = MockPhysicsEngine()
    
    def test_ball_mass_update(self):
        params = {'ball_mass': 5.0}
        self.capture.update_physics_params(params, save=False)
        self.assertEqual(self.capture.physics_engine.config.ball_mass, 5.0)

    def test_rail_params_update(self):
        params = {
            'rail_x_offset': 10.0,
            'rail_y_offset': -5.0,
            'guide_thickness': 2.0
        }
        self.capture.update_physics_params(params, save=False)
        config = self.capture.physics_engine.config
        self.assertEqual(config.rail_x_offset, 10.0)
        self.assertEqual(config.rail_y_offset, -5.0)
        self.assertEqual(config.guide_thickness, 2.0)

    def test_combo_settings_update(self):
        params = {'combo_window': 2.5}
        self.capture.update_physics_params(params, save=False)
        self.assertEqual(self.capture.physics_engine.config.combo_window, 2.5)

    def test_nudge_cost_update(self):
        params = {'nudge_cost': 500}
        self.capture.update_physics_params(params, save=False)
        # Nudge cost is stored in capture AND engine config (potentially)
        self.assertEqual(self.capture.nudge_cost, 500.0)
        self.assertEqual(self.capture.physics_engine.config.nudge_cost, 500.0)

    def test_tilt_threshold_update(self):
        params = {'tilt_threshold': 2000.0}
        self.capture.update_physics_params(params, save=False)
        self.assertEqual(self.capture.tilt_threshold, 2000.0)

if __name__ == '__main__':
    unittest.main()
