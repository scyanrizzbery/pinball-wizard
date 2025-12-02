import unittest
import numpy as np
from unittest.mock import MagicMock
from pbwizard.environment import PinballEnv
from pbwizard.constants import ACTION_NOOP, ACTION_FLIP_LEFT, ACTION_FLIP_RIGHT, ACTION_FLIP_BOTH

class MockVision:
    def __init__(self):
        self.zone_manager = MagicMock()
        self.zone_manager.get_zone_status.return_value = {'left': True, 'right': True}
        self.ball_lost = False
        self.width = 640
        self.height = 480
    
    def get_frame(self):
        return np.zeros((480, 640, 3), dtype=np.uint8)

    def get_raw_frame(self):
        return np.zeros((480, 640, 3), dtype=np.uint8)
        
    def process_frame(self, frame):
        return (320, 240), frame
        
    def get_score(self):
        return 100

    def check_zones(self, x, y):
        return self.zone_manager.get_zone_status(x, y)

class TestEnvironment(unittest.TestCase):
    def setUp(self):
        self.vision = MockVision()
        self.hw = MagicMock()
        self.score_reader = MagicMock()
        self.env = PinballEnv(self.vision, self.hw, self.score_reader)
        self.env.reset()

    def test_env_step_actions(self):
        # Fake last ball pos for zone check
        self.env.last_ball_pos = (320, 240)
        
        # Test Left Flip
        self.env.step(ACTION_FLIP_LEFT)
        self.hw.hold_left.assert_called_once()
        self.hw.release_right.assert_called_once()
        self.hw.reset_mock()
        
        # Test Right Flip
        self.env.step(ACTION_FLIP_RIGHT)
        self.hw.release_left.assert_called_once()
        self.hw.hold_right.assert_called_once()
        self.hw.reset_mock()
        
        # Test Both Flip
        self.env.step(ACTION_FLIP_BOTH)
        self.hw.hold_left.assert_called_once()
        self.hw.hold_right.assert_called_once()
        self.hw.reset_mock()
        
        # Test No-Op
        self.env.step(ACTION_NOOP)
        self.hw.release_left.assert_called_once()
        self.hw.release_right.assert_called_once()

    def test_env_zone_restrictions(self):
        # Ball NOT in left zone, but IN right zone
        self.vision.zone_manager.get_zone_status.return_value = {'left': False, 'right': True}
        self.env.last_ball_pos = (320, 240)
        
        # Ensure safety override doesn't trigger:
        # Safety checks for vy > 50. We need to mock get_ball_status or ensure vy is low.
        # The env calculates vy from last_ball_pos if get_ball_status is missing.
        # Let's mock get_ball_status to return 0 velocity
        self.vision.get_ball_status = MagicMock(return_value=((320, 240), (0, 0)))

        # Try Left Flip -> Should be blocked (No-Op)
        self.env.step(ACTION_FLIP_LEFT)
        self.hw.hold_left.assert_not_called()
        self.hw.release_left.assert_called() # No-op releases
        self.hw.reset_mock()
        
        # Try Both Flip -> Should downgrade to Right Flip
        self.env.step(ACTION_FLIP_BOTH)
        self.hw.hold_left.assert_not_called()
        self.hw.hold_right.assert_called()
        self.hw.reset_mock()

    def test_env_reward(self):
        # Initial score is 0 (from reset)
        # Mock vision returns 100
        obs, reward, terminated, truncated, info = self.env.step(ACTION_NOOP)
        
        # Reward = (100 - 0)/100 + 0.2 (survival) = 1.2
        # Also potentially height reward? 
        # Ball pos is (320, 240) from MockVision. Height is 480.
        # y_ratio = 240/480 = 0.5. Height reward = (1 - 0.5) * 0.1 = 0.05.
        # Total = 1.2 + 0.05 = 1.25
        self.assertAlmostEqual(reward, 1.25) 
        self.assertFalse(terminated)
        
        # Next step, score still 100
        obs, reward, terminated, truncated, info = self.env.step(ACTION_NOOP)
        # Reward = 0 + 0.2 + 0.05 = 0.25
        self.assertAlmostEqual(reward, 0.25)

if __name__ == "__main__":
    unittest.main()
