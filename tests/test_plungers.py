import unittest
import numpy as np
from unittest.mock import MagicMock
from pbwizard.physics import PymunkEngine
from pbwizard.vision import SimulatedFrameCapture

class MockEngine(PymunkEngine):
    def _setup_collision_logging(self):
        # Simulate broken handler or manually disabled for isolation
        pass
    
    def _setup_slingshots(self):
        pass

class TestPlungers(unittest.TestCase):
    def setUp(self):
        class MockLayout:
            def __init__(self):
                self.left_flipper_x_min = 0.3
                self.left_flipper_y_max = 0.8
                self.right_flipper_x_max = 0.7
                self.right_flipper_y_max = 0.8
                self.bumpers = []
                self.drop_targets = []
                self.rails = []
            
        self.layout = MockLayout()
        self.width = 100
        self.height = 200
        # Use subclass to disable collision logic
        self.engine = MockEngine(self.layout, self.width, self.height)

    def test_left_plunger_auto_fire(self):
        # Place ball in left plunger lane
        # Left lane is < 0.15 * width (< 15)
        # Height > 0.5 * height (> 100)
        
        # Add ball at (10, 180) - clearly in zone
        # Add ball at (10, 185) - clearly in zone
        self.engine.add_ball((10, 185))
        self.engine.space.step(0.016)
        ball = self.engine.balls[-1]
        # Zero velocity to simulate stationary
        ball.velocity = (0, 0)
        
        # Ensure left plunger is resting
        self.engine.left_plunger_state = 'resting'
        
        # Run update
        # Should trigger auto-fire
        self.engine.update(0.016)
        
        # Verify state changed to firing
        self.assertEqual(self.engine.left_plunger_state, 'firing')
        
        # Verify ball was activated (though hard to test directly via pymunk state easily without moving)
        # But state change confirms logic execution

    def test_left_plunger_no_fire_when_moving(self):
        # Ball moving fast in lane
        self.engine.add_ball((10, 180))
        self.engine.space.step(0.016)
        ball = self.engine.balls[-1]
        ball.velocity = (0, 200) # Moving fast down
        print(f"DEBUG TEST: Ball Velocity set to {ball.velocity}, Length: {ball.velocity.length}")
        
        self.engine.left_plunger_state = 'resting'
        self.engine.update(0.016)
        
        # Should NOT fire
        self.assertEqual(self.engine.left_plunger_state, 'resting')

    def test_left_plunger_no_fire_outside_zone(self):
        # Ball stationary but outside zone
        self.engine.add_ball((50, 180)) # Center
        self.engine.space.step(0.016)
        ball = self.engine.balls[-1]
        ball.velocity = (0, 0)
        
        self.engine.left_plunger_state = 'resting'
        self.engine.update(0.016)
        
        self.assertEqual(self.engine.left_plunger_state, 'resting')

if __name__ == "__main__":
    unittest.main()
