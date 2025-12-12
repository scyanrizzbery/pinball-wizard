
import unittest
from unittest.mock import MagicMock, patch
from pbwizard.vision import SimulatedFrameCapture

@patch('pbwizard.vision.PymunkEngine')
class TestGameRules(unittest.TestCase):
    def setUp(self):
        # We don't need to do much here since we patch PymunkEngine
        pass

    def test_initial_state(self, MockEngine):
        """Test that game starts at Ball 1."""
        vision = SimulatedFrameCapture()
        # Mock instance returned by constructor
        mock_engine = MockEngine.return_value
        # Fix: Ensure score is int to prevent comparison error
        mock_engine.score = 0
        mock_engine.is_tilted = False
        mock_engine.drop_target_states = []
        
        vision.reset_game_state()
        self.assertEqual(vision.current_ball, 1)
        self.assertFalse(vision.game_over)
        
        # Verify initial ball added (called on the instance created by reset_game_state)
        mock_engine.add_ball.assert_called()

    def test_ball_drain_sequence(self, MockEngine):
        """Test the 1 -> 2 -> 3 -> Game Over sequence."""
        vision = SimulatedFrameCapture()
        vision.reset_game_state()
        
        # Get the mock engine instance currently in use
        mock_engine = vision.physics_engine
        # Fix: Ensure score is int
        mock_engine.score = 0
        mock_engine.is_tilted = False
        
        self.assertEqual(vision.current_ball, 1)
        
        # Simulate Ball 1 Draining
        # manual_step checks if no balls in physics engine
        mock_engine.balls = [] 
        vision.respawn_timer = 0
        
        # Run step (dt=0.1)
        vision.manual_step(0.1, render=False)
        
        # Should be Ball 2 now
        self.assertEqual(vision.current_ball, 2)
        self.assertFalse(vision.game_over)
        # Should set respawn cooldown
        self.assertGreater(vision.respawn_timer, 0)
        
        # Clear cooldown to simulate wait
        vision.respawn_timer = 0
        
        # Simulate Ball 2 draining
        vision.manual_step(0.1, render=False)
        self.assertEqual(vision.current_ball, 3)
        self.assertFalse(vision.game_over)
        
        # Clear cooldown
        vision.respawn_timer = 0
        
        # Simulate Ball 3 draining
        vision.manual_step(0.1, render=False)
        # Should be Game Over
        self.assertTrue(vision.game_over)
        # Ball count shouldn't increase beyond 3 (or just stays at 3 with game over)
        self.assertEqual(vision.current_ball, 3)

    def test_reset_clears_state(self, MockEngine):
        """Test that reset_game_state clears counters."""
        vision = SimulatedFrameCapture()
        vision.current_ball = 3
        vision.game_over = True
        
        vision.reset_game_state()
        
        self.assertEqual(vision.current_ball, 1)
        self.assertFalse(vision.game_over)

if __name__ == '__main__':
    unittest.main()
