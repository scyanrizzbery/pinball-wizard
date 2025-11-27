import pytest
import numpy as np
from unittest.mock import MagicMock
from pbwizard.environment import PinballEnv
from pbwizard.constants import ACTION_NOOP, ACTION_FLIP_LEFT, ACTION_FLIP_RIGHT, ACTION_FLIP_BOTH

class MockVision:
    def __init__(self):
        self.zones = MagicMock()
        self.zones.get_zone_status.return_value = {'left': True, 'right': True}
        self.ball_lost = False
    
    def get_frame(self):
        return np.zeros((480, 640, 3), dtype=np.uint8)
        
    def process_frame(self, frame):
        return (320, 240), frame
        
    def get_score(self):
        return 100

def test_env_step_actions():
    vision = MockVision()
    hw = MagicMock()
    score_reader = MagicMock()
    
    env = PinballEnv(vision, hw, score_reader)
    env.reset()
    
    # Fake last ball pos for zone check
    env.last_ball_pos = (320, 240)
    
    # Test Left Flip
    env.step(ACTION_FLIP_LEFT)
    hw.hold_left.assert_called_once()
    hw.release_right.assert_called_once()
    hw.reset_mock()
    
    # Test Right Flip
    env.step(ACTION_FLIP_RIGHT)
    hw.release_left.assert_called_once()
    hw.hold_right.assert_called_once()
    hw.reset_mock()
    
    # Test Both Flip
    env.step(ACTION_FLIP_BOTH)
    hw.hold_left.assert_called_once()
    hw.hold_right.assert_called_once()
    hw.reset_mock()
    
    # Test No-Op
    env.step(ACTION_NOOP)
    hw.release_left.assert_called_once()
    hw.release_right.assert_called_once()

def test_env_zone_restrictions():
    vision = MockVision()
    # Ball NOT in left zone, but IN right zone
    vision.zones.get_zone_status.return_value = {'left': False, 'right': True}
    
    hw = MagicMock()
    score_reader = MagicMock()
    
    env = PinballEnv(vision, hw, score_reader)
    env.reset()
    env.last_ball_pos = (320, 240)
    
    # Try Left Flip -> Should be blocked (No-Op)
    env.step(ACTION_FLIP_LEFT)
    hw.hold_left.assert_not_called()
    hw.release_left.assert_called() # No-op releases
    hw.reset_mock()
    
    # Try Both Flip -> Should downgrade to Right Flip
    env.step(ACTION_FLIP_BOTH)
    hw.hold_left.assert_not_called()
    hw.hold_right.assert_called()
    hw.reset_mock()

def test_env_reward():
    vision = MockVision()
    hw = MagicMock()
    score_reader = MagicMock()
    
    env = PinballEnv(vision, hw, score_reader)
    env.reset()
    
    # Initial score is 0 (from reset)
    # Mock vision returns 100
    obs, reward, terminated, truncated, info = env.step(ACTION_NOOP)
    
    assert reward == 100 # 100 - 0
    assert not terminated
    
    # Next step, score still 100
    obs, reward, terminated, truncated, info = env.step(ACTION_NOOP)
    assert reward == 0 # 100 - 100
