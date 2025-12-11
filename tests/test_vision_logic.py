
import pytest
from unittest.mock import MagicMock, patch
import sys

# Mock cv2 before importing vision
sys.modules['cv2'] = MagicMock()

from pbwizard.vision import SimulatedFrameCapture, PinballLayout

class MockPhysicsEngine:
    def __init__(self):
        self.balls = []
        self.auto_plunge_enabled = True
        self.score = 0
        self.drop_target_states = []
        self.is_tilted = False
    
    def add_ball(self, pos):
        pass

    def update(self, dt):
        pass

def test_auto_launch_does_not_wait():
    # Setup
    with patch('pbwizard.vision.PymunkEngine') as MockEngine:
        # Mock engine instance
        mock_engine_instance = MockPhysicsEngine()
        MockEngine.return_value = mock_engine_instance
        
        vision = SimulatedFrameCapture(width=100, height=200)
        # Force the mock engine we can control
        vision.physics_engine = mock_engine_instance
        vision.physics_engine.auto_plunge_enabled = True # Runtime set to True
        
        # Override config logic that might have happened in init
        vision.layout.config = {'auto_plunge_enabled': False} 
        vision.layout.physics_params = {'auto_plunge_enabled': False}
        
        vision.game_over = False
        vision.current_ball = 1
        vision.respawn_timer = 0
        vision.waiting_for_launch = False
        
        # Act: Simulate frame where ball is lost
        vision.manual_step(dt=0.016)
        
        # Assert
        # If waiting_for_launch is True, it means the logic ignored the runtime flag
        assert vision.waiting_for_launch is False, "Should not be waiting for launch if auto_plunge_enabled is True"

def test_manual_launch_waits_if_disabled():
    # Setup
    with patch('pbwizard.vision.PymunkEngine') as MockEngine:
        mock_engine_instance = MockPhysicsEngine()
        MockEngine.return_value = mock_engine_instance
        
        vision = SimulatedFrameCapture(width=100, height=200)
        vision.physics_engine = mock_engine_instance
        vision.physics_engine.auto_plunge_enabled = False # Logic disabled
        
        vision.layout.config = {'auto_plunge_enabled': False}
        
        vision.game_over = False
        vision.current_ball = 1
        vision.respawn_timer = 0
        vision.waiting_for_launch = False
        
        # Act
        vision.manual_step(dt=0.016)
        
        # Assert
        assert vision.waiting_for_launch is True, "Should be waiting for launch if auto_plunge_enabled is False"
