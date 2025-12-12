
import unittest
import numpy as np
from unittest.mock import MagicMock
from pbwizard.environment import PinballEnv
from pbwizard import constants

class TestNudgeLogic(unittest.TestCase):
    def test_plunger_lane_ignore(self):
        # Mock dependencies
        vision = MagicMock()
        hw = MagicMock()
        score_reader = MagicMock()
        
        # Setup Env
        env = PinballEnv(vision, hw, score_reader, headless=True)
        
        # Mock vision.get_ball_status directly because MagicMock has all attributes
        width = 1000
        height = 1000
        vision.get_ball_status.return_value = ((850.0, 900.0), (0.0, 0.0))
        vision.get_score.return_value = 0
        vision.capture.physics_engine.get_combo_status.return_value = {'combo_count': 0, 'combo_active': False}
        vision.capture.physics_engine.get_multiplier.return_value = 1.0
        vision.capture.width = width
        vision.capture.height = height
        vision.get_frame.return_value = None
        
        # Reset env
        env.reset()
        
        # Step 10 times
        for _ in range(10):
            env.step(0)
            
        # Check holding_steps
        print(f"Holding Steps (Plunger Lane): {env.holding_steps}")
        self.assertEqual(env.holding_steps, 0, "Holding steps should be 0 in plunger lane")
        
        # Now move ball to playfield (x < 800) and stationary
        vision.get_ball_status.return_value = ((500.0, 500.0), (0.0, 0.0))
        
        # Step 10 times
        for _ in range(10):
            env.step(0)
            
        print(f"Holding Steps (Playfield): {env.holding_steps}")
        self.assertGreater(env.holding_steps, 0, "Holding steps should increment in playfield")
        
if __name__ == '__main__':
    unittest.main()
