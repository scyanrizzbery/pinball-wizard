import unittest
import numpy as np
from pbwizard.vision import SimulatedFrameCapture
from pbwizard.environment import PinballEnv
from pbwizard.hardware import MockController
from pbwizard.vision import BallTracker, ZoneManager

class TestNudge(unittest.TestCase):
    def test_nudge_action(self):
        # Setup minimal environment components
        sim = SimulatedFrameCapture(headless=True)
        
        # Mock VisionWrapper
        class MockVisionWrapper:
            def __init__(self, capture):
                self.capture = capture
                self.zone_manager = ZoneManager(800, 600)
                self.auto_start_enabled = False
            
            def get_frame(self):
                return self.capture.get_frame()
        
        vision = MockVisionWrapper(sim)
        hw = MockController(vision_system=sim) # Connect mock hw to sim
        score_reader = None
        
        env = PinballEnv(vision, hw, score_reader, headless=True)
        
        # Add a ball manually
        sim.add_ball()
        ball = sim.balls[0]
        ball['vel'] = np.array([0.0, 0.0]) # Stop the ball
        
        initial_vel = ball['vel'].copy()
        print(f"Initial Velocity: {initial_vel}")
        
        # Perform Nudge Left (Action 4)
        # Nudge Left pushes table left, imparting force? 
        # In our implementation: nudge(-5, -2) -> vel += (-5, -2)
        env.step(4)
        
        vel_after_nudge = ball['vel'].copy()
        print(f"Velocity after Nudge Left: {vel_after_nudge}")
        
        # Verify velocity changed significantly in X and Y
        self.assertNotEqual(vel_after_nudge[0], initial_vel[0])
        self.assertLess(vel_after_nudge[0], initial_vel[0]) # Should be negative (left)
        
        # Reset velocity
        ball['vel'] = np.array([0.0, 0.0])
        
        # Perform Nudge Right (Action 5)
        # nudge(5, -2) -> vel += (5, -2)
        env.step(5)
        
        vel_after_nudge_right = ball['vel'].copy()
        print(f"Velocity after Nudge Right: {vel_after_nudge_right}")
        
        self.assertGreater(vel_after_nudge_right[0], 0) # Should be positive (right)

        print("Nudge mechanics verified!")

if __name__ == '__main__':
    unittest.main()
