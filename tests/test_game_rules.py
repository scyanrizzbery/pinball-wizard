
import unittest
from unittest.mock import MagicMock
from pbwizard.vision import SimulatedFrameCapture

class TestGameRules(unittest.TestCase):
    def setUp(self):
        # minimal mock for SimulatedFrameCapture
        self.vision = SimulatedFrameCapture()
        # Mock physics engine
        self.vision.physics_engine = MagicMock()
        self.vision.physics_engine.balls = [] 
        self.vision.physics_engine.score = 0 # Ensure int
        self.vision.score = 0 # Ensure int
        self.vision.high_score = 0 # Ensure int
        # Mock layout
        self.vision.layout = MagicMock()
        self.vision.layout.drop_targets = []

    def test_initial_state(self):
        """Test that game starts at Ball 1."""
        self.vision.reset_game_state()
        self.assertEqual(self.vision.current_ball, 1)
        self.assertFalse(self.vision.game_over)
        # Verify initial ball added
        self.vision.physics_engine.add_ball.assert_called()

    def test_ball_drain_sequence(self):
        """Test the 1 -> 2 -> 3 -> Game Over sequence."""
        self.vision.reset_game_state()
        self.assertEqual(self.vision.current_ball, 1)
        
        # Simulate Ball 1 Draining
        # manual_step checks if no balls in physics engine
        self.vision.physics_engine.balls = [] 
        self.vision.respawn_timer = 0
        
        # Run step (dt=0.1)
        self.vision.manual_step(0.1)
        
        # Should be Ball 2 now
        self.assertEqual(self.vision.current_ball, 2)
        self.assertFalse(self.vision.game_over)
        # Should set respawn cooldown
        self.assertGreater(self.vision.respawn_timer, 0)
        
        # Clear cooldown to simulate wait
        self.vision.respawn_timer = 0
        
        # Simulate Ball 2 draining
        self.vision.manual_step(0.1)
        self.assertEqual(self.vision.current_ball, 3)
        self.assertFalse(self.vision.game_over)
        
        # Clear cooldown
        self.vision.respawn_timer = 0
        
        # Simulate Ball 3 draining
        self.vision.manual_step(0.1)
        # Should be Game Over
        self.assertTrue(self.vision.game_over)
        # Ball count shouldn't increase beyond 3 (or just stays at 3 with game over)
        self.assertEqual(self.vision.current_ball, 3)

    def test_reset_clears_state(self):
        """Test that reset_game_state clears counters."""
        self.vision.current_ball = 3
        self.vision.game_over = True
        
        self.vision.reset_game_state()
        
        self.assertEqual(self.vision.current_ball, 1)
        self.assertFalse(self.vision.game_over)

if __name__ == '__main__':
    unittest.main()
