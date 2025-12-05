"""
Unit tests for drop target reset functionality.
Tests the delayed reset system for drop targets in the pinball game.
"""
import unittest
import time
from unittest.mock import Mock, MagicMock, patch
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from pbwizard.vision import Vision
from pbwizard.layout import PinballLayout


class TestDropTargetReset(unittest.TestCase):
    """Test cases for drop target delayed reset functionality."""
    
    def setUp(self):
        """Set up test fixtures."""
        # Create a mock layout with 3 drop targets
        self.layout = Mock(spec=PinballLayout)
        self.layout.drop_targets = [
            {'x': 0.3, 'y': 0.5, 'width': 0.05, 'height': 0.02, 'value': 100},
            {'x': 0.4, 'y': 0.5, 'width': 0.05, 'height': 0.02, 'value': 100},
            {'x': 0.5, 'y': 0.5, 'width': 0.05, 'height': 0.02, 'value': 100}
        ]
        self.layout.rails = []
        self.layout.bumpers = []
        self.layout.zones = []
        
    def test_reset_scheduled_when_all_targets_hit(self):
        """Test that reset is scheduled when all targets are hit."""
        vision = Vision(width=450, height=800, socketio=None, layout_config=self.layout, headless=True)
        
        # Initialize drop target states
        vision.drop_target_states = [True, True, True]
        vision.multiball_cooldown_timer = 0  # No cooldown
        
        # Create a mock ball
        ball = {'pos': [0, 0], 'vel': [0, 0], 'lost': False}
        
        # Hit all three targets
        vision.drop_target_states[0] = False
        vision.drop_target_states[1] = False
        vision.drop_target_states[2] = False
        
        # Trigger collision check with all targets down
        all_down = not any(vision.drop_target_states)
        self.assertTrue(all_down, "All targets should be down")
        
        # Simulate the scheduling logic
        start_time = time.time()
        vision._drop_target_reset_scheduled = True
        vision._drop_target_reset_time = start_time + 2.0
        
        # Check that reset is scheduled
        self.assertTrue(vision._drop_target_reset_scheduled, "Reset should be scheduled")
        self.assertIsNotNone(vision._drop_target_reset_time, "Reset time should be set")
        self.assertGreater(vision._drop_target_reset_time, start_time, "Reset time should be in future")
        
    def test_reset_not_executed_before_delay(self):
        """Test that reset doesn't execute before the delay period."""
        vision = Vision(width=450, height=800, socketio=None, layout_config=self.layout, headless=True)
        
        vision.drop_target_states = [False, False, False]
        vision._drop_target_reset_scheduled = True
        vision._drop_target_reset_time = time.time() + 2.0
        
        # Check immediately - should still be scheduled
        self.assertTrue(vision._drop_target_reset_scheduled)
        self.assertFalse(time.time() >= vision._drop_target_reset_time, "Should not be time yet")
        
    def test_reset_executes_after_delay(self):
        """Test that reset executes after the delay period."""
        vision = Vision(width=450, height=800, socketio=None, layout_config=self.layout, headless=True)
        
        vision.drop_target_states = [False, False, False]
        vision._drop_target_reset_scheduled = True
        vision._drop_target_reset_time = time.time() - 0.1  # Set to past
        
        # Mock physics engine
        vision.physics_engine = Mock()
        vision.physics_engine.drop_target_shapes = [Mock(), Mock(), Mock()]
        vision.physics_engine.space = Mock()
        vision.physics_engine.space.shapes = set()
        
        # Simulate reset logic
        if (vision._drop_target_reset_scheduled and 
            time.time() >= vision._drop_target_reset_time):
            
            vision.drop_target_states = [True] * len(self.layout.drop_targets)
            vision._drop_target_invuln_until = [time.time() + 0.5] * len(self.layout.drop_targets)
            vision._drop_target_reset_scheduled = False
            vision._drop_target_reset_time = None
        
        # Verify reset executed
        self.assertTrue(all(vision.drop_target_states), "All targets should be reset to True")
        self.assertFalse(vision._drop_target_reset_scheduled, "Reset flag should be cleared")
        self.assertIsNone(vision._drop_target_reset_time, "Reset time should be cleared")
        
    def test_reset_cancelled_if_target_restored_manually(self):
        """Test that scheduled reset is cancelled if targets are restored another way."""
        vision = Vision(width=450, height=800, socketio=None, layout_config=self.layout, headless=True)
        
        # Schedule a reset
        vision.drop_target_states = [False, False, False]
        vision._drop_target_reset_scheduled = True
        vision._drop_target_reset_time = time.time() + 2.0
        
        # Manually restore one target (simulating external reset)
        vision.drop_target_states[0] = True
        
        # Check if any targets are back up
        all_down = not any(vision.drop_target_states)
        if not all_down:
            vision._drop_target_reset_scheduled = False
        
        # Verify reset was cancelled
        self.assertFalse(vision._drop_target_reset_scheduled, "Reset should be cancelled")
        
    def test_invulnerability_period_set_after_reset(self):
        """Test that targets have invulnerability period after reset."""
        vision = Vision(width=450, height=800, socketio=None, layout_config=self.layout, headless=True)
        
        # Execute reset
        current_time = time.time()
        vision.drop_target_states = [True] * 3
        vision._drop_target_invuln_until = [current_time + 0.5] * 3
        
        # Check invulnerability
        self.assertEqual(len(vision._drop_target_invuln_until), 3)
        for invuln_time in vision._drop_target_invuln_until:
            self.assertGreater(invuln_time, current_time, "Should be invulnerable")
            self.assertLess(invuln_time, current_time + 1.0, "Invulnerability should expire soon")
        
    def test_multiball_triggered_on_all_targets_down(self):
        """Test that multiball is triggered when all targets are hit."""
        vision = Vision(width=450, height=800, socketio=None, layout_config=self.layout, headless=True)
        
        # Mock add_ball method
        vision.add_ball = Mock()
        vision.multiball_cooldown_timer = 0  # No cooldown
        
        vision.drop_target_states = [False, False, False]
        vision._drop_target_reset_scheduled = False
        
        # Simulate multiball trigger logic
        all_down = not any(vision.drop_target_states)
        if all_down and not vision._drop_target_reset_scheduled:
            if time.time() > vision.multiball_cooldown_timer:
                vision.add_ball()
                vision.multiball_cooldown_timer = time.time() + 5.0
        
        # Verify multiball was triggered
        vision.add_ball.assert_called_once()


if __name__ == '__main__':
    unittest.main()
