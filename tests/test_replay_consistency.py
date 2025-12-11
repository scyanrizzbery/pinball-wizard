import unittest
import sys
import os
import random
import time

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pbwizard.vision import SimulatedFrameCapture

class TestReplayConsistency(unittest.TestCase):
    def test_replay_score_matches_original(self):
        # 1. Setup Headless Simulation
        os.environ['HEADLESS_SIM'] = 'true'
        cap = SimulatedFrameCapture(width=600, height=800)
        
        # 2. Start a fresh game
        print("Starting Original Game...")
        cap.reset_game_state()
        
        # 3. Simulate Game with Random Inputs
        # We need enough frames to get some score
        frames_to_sim = 300 # 5 seconds at 60fps
        
        for i in range(frames_to_sim):
            # Randomly flip every ~60 frames
            if i % 60 == 10:
                cap.trigger_left()
            if i % 60 == 40:
                cap.release_left()
                
            if i % 45 == 5:
                cap.trigger_right()
            if i % 45 == 35:
                cap.release_right()
                
            cap.manual_step()
            
        original_score = cap.score
        print(f"Original Game Finished. Score: {original_score}")
        
        # 4. Extract Replay Data
        # We need to manually construct what save_replay would produce or use the internal data
        # save_replay writes to disk, we just want the dict
        replay_data = cap.replay_manager.replay_data.copy()
        # Ensure seed is recorded (it's in replay_data['seed'] set by start_recording inside _init_physics)
        print(f"Replay Data Seed: {replay_data.get('seed')}")
        print(f"Replay Events: {len(replay_data.get('events', []))}")
        
        # 5. Load Replay
        print("Loading Replay...")
        success = cap.handle_load_replay(replay_data)
        self.assertTrue(success, "Failed to load replay")
        
        self.assertTrue(cap.replay_manager.is_playing, "Replay should be playing after load")
        
        # 6. Run Replay
        # We run for the same number of frames
        print("Running Replay...")
        replay_score = 0
        
        for i in range(frames_to_sim):
            cap.manual_step()
            replay_score = cap.score
            
        print(f"Replay Finished. Score: {replay_score}")
        
        # 7. Compare Scores
        self.assertEqual(original_score, replay_score, 
                         f"Replay score ({replay_score}) does not match original score ({original_score})")

if __name__ == '__main__':
    unittest.main()
