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
        self.vision.capture.height = 800
        self.vision.capture.width = 450
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
        
        # Expect 0.1 survival reward (medium difficulty default)
        self.assertAlmostEqual(reward, 0.1)
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
        
        # Expect (500/50) + 0.1 = 10.1 (updated from /100 to /50)
        self.assertAlmostEqual(reward, 10.1)

    def test_loss_penalty(self):
        # Mock ball lost (y > height * 0.98)
        frame = np.zeros((800, 450, 3), dtype=np.uint8)
        height = 800
        self.vision.get_frame.return_value = frame
        self.vision.get_raw_frame.return_value = frame
        # Ball at 790 (height is 800, 0.98 * 800 = 784). So 790 is lost.
        self.vision.process_frame.return_value = ((225, 790), np.zeros((800, 450, 3))) 
        # Also mock get_ball_status because headless=True skips process_frame result usage for ball_pos
        self.vision.get_ball_status.return_value = ((225, 790), (0, 0))
        
        self.vision.get_score.return_value = 0
        self.env.current_score = 0
        self.env.last_score = 0
        
        # Ensure vision.ball_lost is False initially, but env checks position
        self.vision.ball_lost = False
        
        # Step
        _, reward, terminated, _, _ = self.env.step(0)
        
        # Expect -50.0 (drain penalty) + 0.1 (survival) + height reward
        # Height reward: (1 - 790/800) * 0.2 = 0.0025
        # Total: -50.0 + 0.1 + 0.0025 = -49.8975
        self.assertTrue(terminated)
        self.assertAlmostEqual(reward, -49.8975, places=3)

    def test_combo_and_multiplier_rewards(self):
        """Test that combo count and multipliers properly reward the AI."""
        frame = np.zeros((800, 450, 3), dtype=np.uint8)
        self.vision.get_frame.return_value = frame
        self.vision.get_raw_frame.return_value = frame
        self.vision.process_frame.return_value = ((225, 400), np.zeros((800, 450, 3)))

        # Mock physics engine with combo status
        mock_physics = MagicMock()
        mock_physics.get_combo_status.return_value = {
            'combo_count': 4,
            'combo_active': True,
            'combo_timer': 2.5
        }
        mock_physics.get_multiplier.return_value = 4.0

        self.vision.capture.physics_engine = mock_physics

        # Mock score increase (base 100 points * 4x multiplier = 400 points)
        self.vision.get_score.return_value = 400
        self.env.current_score = 0
        self.env.last_score = 0

        # Step
        _, reward, _, _, _ = self.env.step(0)

        # Expected rewards:
        # - Score: 400 / 50 = 8.0
        # - Survival: 0.1
        # - Combo: 1.0 * 4 = 4.0
        # - Multiplier bonus: (4.0 - 1.0) * 0.5 = 1.5
        # Total: 8.0 + 0.1 + 4.0 + 1.5 = 13.6
        self.assertAlmostEqual(reward, 13.6, places=1)

if __name__ == '__main__':
    unittest.main()
