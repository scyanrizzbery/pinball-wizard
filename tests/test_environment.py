import unittest
import numpy as np
from unittest.mock import MagicMock
from pbwizard.environment import PinballEnv
from pbwizard.constants import ACTION_NOOP, ACTION_FLIP_LEFT, ACTION_FLIP_RIGHT, ACTION_FLIP_BOTH

class MockVision:
    def __init__(self):
        self.ball_lost = False
        self.width = 640
        self.height = 480
        # Mock physics engine for combo/multiplier checks
        self.capture = MagicMock()
        self.capture.physics_engine.get_combo_status.return_value = {
            'combo_count': 0, 'combo_active': False, 'combo_timer': 0.0
        }
        self.capture.physics_engine.get_multiplier.return_value = 1.0
        self.capture.get_ball_status.return_value = None

    def get_frame(self):
        return np.zeros((480, 640, 3), dtype=np.uint8)

    def get_raw_frame(self):
        return np.zeros((480, 640, 3), dtype=np.uint8)
        
    def process_frame(self, frame):
        return (320, 240), frame
        
    def get_score(self):
        return 100



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

    def test_env_reward(self):
        # Initial score is 0 (from reset)
        # Mock vision returns 100
        obs, reward, terminated, truncated, info = self.env.step(ACTION_NOOP)
        
        # Reward = log1p(100) * 0.106 + survival (0.005) + height (~0.005)
        self.assertAlmostEqual(reward, 0.497, places=3)
        self.assertFalse(terminated)
        
        # Next step, score still 100
        obs, reward, terminated, truncated, info = self.env.step(ACTION_NOOP)
        # Reward = survival + height reward only (no score delta)
        self.assertAlmostEqual(reward, 0.0075, places=3)

    def test_stuck_ball_detection(self):
        # Setup specific mock for ball status (stationary)
        # Using vision.get_ball_status fallback
        self.vision.get_ball_status = MagicMock(return_value=((100, 100), (0, 0))) # Velocity 0
        self.vision.capture.get_ball_status.return_value = ((100, 100), (0, 0))
        
        # Difficulty Medium -> Threshold 90 (Tuned values)
        # Trigger at 90 + 20 = 110 steps
        
        # Run 110 steps
        for _ in range(110):
            self.env.step(ACTION_NOOP)
            
        self.assertEqual(self.env.holding_steps, 110)
        self.vision.capture.nudge_left.assert_not_called()
        self.vision.capture.nudge_right.assert_not_called()
        
        # Step 111 -> Triggers Stuck Ball Logic
        self.env.step(ACTION_NOOP)
        
        # holding_steps should be reset
        self.assertEqual(self.env.holding_steps, 0)
        
        # Verify Nudge was called (Left or Right)
        # We don't know which one due to random choice, but one should be called
        nudge_left_called = self.vision.capture.nudge_left.called
        nudge_right_called = self.vision.capture.nudge_right.called
        self.assertTrue(nudge_left_called or nudge_right_called, "One of the nudge methods should be called")

if __name__ == "__main__":
    unittest.main()
