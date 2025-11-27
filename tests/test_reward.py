import unittest
import numpy as np
import sys
import os
from unittest.mock import MagicMock

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from pbwizard.environment import PinballEnv

class TestRewardShaping(unittest.TestCase):
    def setUp(self):
        self.vision = MagicMock()
        self.hw = MagicMock()
        self.score_reader = MagicMock()
        self.env = PinballEnv(self.vision, self.hw, self.score_reader, headless=True)
        # Ensure get_ball_status returns None so it falls back to process_frame
        self.vision.get_ball_status.return_value = None
        self.vision.capture.get_ball_status.return_value = None
        self.vision.ball_lost = False
        self.vision.capture.ball_lost = False
        
    def test_survival_reward(self):
        # Mock vision to return a frame and ball position
        frame = np.zeros((800, 450, 3), dtype=np.uint8)
        self.vision.get_frame.return_value = frame
        self.vision.get_raw_frame.return_value = frame
        self.vision.process_frame.return_value = ((225, 400), np.zeros((800, 450, 3))) # Ball in middle
        self.vision.get_score.return_value = 0 # No score change
        self.env.current_score = 0
        self.env.last_score = 0
        
        # Step
        _, reward, terminated, _, _ = self.env.step(0)
        
        # Expect 0.01 survival reward
        self.assertAlmostEqual(reward, 0.01)
        self.assertFalse(terminated)
        
    def test_score_scaling(self):
        # Mock score increase
        frame = np.zeros((800, 450, 3), dtype=np.uint8)
        self.vision.get_frame.return_value = frame
        self.vision.get_raw_frame.return_value = frame
        self.vision.process_frame.return_value = ((225, 400), np.zeros((800, 450, 3)))
        
        # Mock score update (simulating score reader or vision update)
        # We need to mock _update_score or set vision.get_score if available
        self.vision.get_score.return_value = 500
        
        # Step
        _, reward, _, _, _ = self.env.step(0)
        
        # Expect (500/100) + 0.01 = 5.01
        self.assertAlmostEqual(reward, 5.01)
        
    def test_loss_penalty(self):
        # Mock ball lost (y > height * 0.98)
        frame = np.zeros((800, 450, 3), dtype=np.uint8)
        self.vision.get_frame.return_value = frame
        self.vision.get_raw_frame.return_value = frame
        self.vision.process_frame.return_value = ((225, 790), np.zeros((800, 450, 3))) # Near bottom
        self.vision.get_score.return_value = 0
        self.env.current_score = 0
        self.env.last_score = 0
        
        # Step
        _, reward, terminated, _, _ = self.env.step(0)
        
        # Expect -5.0 + 0.01 = -4.99
        self.assertTrue(terminated)
        self.assertAlmostEqual(reward, -4.99)

if __name__ == '__main__':
    unittest.main()
