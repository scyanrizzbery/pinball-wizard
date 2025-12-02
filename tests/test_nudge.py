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
                self.width = 800
                self.height = 600
            
            def get_frame(self):
                return self.capture.get_frame()
        
        vision = MockVisionWrapper(sim)
        hw = MockController(vision_system=sim) # Connect mock hw to sim
        score_reader = None
        
        env = PinballEnv(vision, hw, score_reader, headless=True)
        
        # Helper to sync balls from physics engine
        def sync_balls():
            state = sim.physics_engine.get_state()
            sim.balls = []
            for b_data in state['balls']:
                 pos_x = b_data['x'] * sim.width
                 pos_y = b_data['y'] * sim.height
                 vel_x = b_data['vx']
                 vel_y = b_data['vy']
                 sim.balls.append({
                     'pos': np.array([pos_x, pos_y]),
                     'vel': np.array([vel_x, vel_y]),
                     'lost': False 
                 })

        # Add a ball manually
        sim.add_ball()
        sync_balls()
        ball = sim.balls[0]
        
        # We can't easily set velocity on the physics body via the dict
        # We need to set it on the physics body directly
        # But for this test, we want to see the effect of nudge on the physics body
        # So we should check physics engine state, or sync back.
        
        # Stop the ball in physics engine
        sim.physics_engine.balls[0].velocity = (0, 0)
        sync_balls()
        ball = sim.balls[0] # Re-get ref
        
        initial_vel = ball['vel'].copy()
        print(f"Initial Velocity: {initial_vel}")
        
        # Perform Nudge Left (Action 4)
        # Nudge Left pushes table left, imparting force? 
        # In our implementation: nudge(-5, -2) -> vel += (-5, -2)
        env.step(4)
        
        # Sync again to see effect
        sync_balls()
        ball = sim.balls[0]
        
        vel_after_nudge = ball['vel'].copy()
        print(f"Velocity after Nudge Left: {vel_after_nudge}")
        
        # Verify velocity changed significantly in X and Y
        self.assertNotEqual(vel_after_nudge[0], initial_vel[0])
        self.assertLess(vel_after_nudge[0], initial_vel[0]) # Should be negative (left)
        
        # Reset velocity
        sim.physics_engine.balls[0].velocity = (0, 0)
        sync_balls()
        
        # Perform Nudge Right (Action 5)
        # nudge(5, -2) -> vel += (5, -2)
        env.step(5)
        
        sync_balls()
        ball = sim.balls[0]
        
        vel_after_nudge_right = ball['vel'].copy()
        print(f"Velocity after Nudge Right: {vel_after_nudge_right}")
        
        self.assertGreater(vel_after_nudge_right[0], 0) # Should be positive (right)

        print("Nudge mechanics verified!")

if __name__ == '__main__':
    unittest.main()
