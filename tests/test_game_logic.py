import unittest
import time
import threading
from pbwizard.vision import SimulatedFrameCapture, BallTracker, ZoneManager
# from play import VisionWrapper  # FIXME: VisionWrapper is in main.py, not a separate module

# Skipping these tests for now as they require VisionWrapper refactoring
@unittest.skip("VisionWrapper needs to be extracted to a testable module")

class TestGameLogic(unittest.TestCase):
    def test_games_played_increment(self):
        # Setup
        cap = SimulatedFrameCapture(width=100, height=100, headless=True)
        tracker = BallTracker()
        zones = ZoneManager(100, 100)
        wrapper = VisionWrapper(cap, tracker, zones)
        
        # Start with 0 games
        stats = wrapper.get_stats()
        self.assertEqual(stats['games_played'], 0)
        
        # Add a ball (Game Start)
        cap.add_ball()
        wrapper.get_frame() # Update tracker/wrapper state
        stats = wrapper.get_stats()
        self.assertEqual(stats['balls'], 1)
        self.assertEqual(wrapper.last_ball_count, 1)
        
        # Remove ball (Game Over)
        with cap.lock:
            cap.balls = []
            
        # Update wrapper
        wrapper.get_frame()
        stats = wrapper.get_stats()
        
        # Verify game count incremented
        self.assertEqual(stats['games_played'], 1)
        self.assertEqual(stats['balls'], 0)
        
    def test_restart_delay(self):
        cap = SimulatedFrameCapture(width=100, height=100, headless=True)
        cap.auto_start_enabled = True
        
        # Start game
        cap.launch_ball()
        self.assertTrue(len(cap.balls) > 0)
        
        # Drain all balls
        with cap.lock:
            cap.balls = []
            
        # Run simulation loop step (manually)
        # We need to simulate the loop logic where it checks for restart
        # Since we can't easily run the threaded loop in sync test, we'll check the logic method if possible
        # or just run the thread and wait.
        
        cap.start()
        time.sleep(0.1) # Let it detect empty balls
        
        # Should NOT have restarted yet (1s delay)
        self.assertEqual(len(cap.balls), 0, "Should wait 1s before restart")
        
        # Wait for delay to pass
        time.sleep(1.1)
        
        # Should have restarted
        self.assertTrue(len(cap.balls) > 0, "Should have auto-restarted after delay")
        
        cap.stop()

if __name__ == '__main__':
    unittest.main()
