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
        # 1. Setup Headless Simulation with Custom Layout
        os.environ['HEADLESS_SIM'] = 'true'
        
        # Create a layout with a bumper right in the middle
        layout_config = {
            'name': 'test_layout',
            'width': 0.6,
            'height': 0.8, # keep ratios simple
            'bumpers': [{'x': 0.5, 'y': 0.5, 'radius_ratio': 0.05}],
            'drop_targets': [],
            'flippers': {}
        }
        
        cap = SimulatedFrameCapture(width=600, height=800, layout_config=layout_config)
    
        # 2. Start a fresh game
        print("Starting Original Game...")
        cap.reset_game_state()
        
        # Hack: Teleport ball to just above the bumper to guarantee a hit
        # Ball 1 is already spawned at plunger. Let's add Ball 2 above bumper to satisfy "score > 0"
        # Wait for physics to settle/spawn first ball
        for _ in range(10): cap.manual_step()
        
        # Add a ball directly above bumper (0.5, 0.4) -> pixel coords (300, 320)
        # Bumper is at (300, 400).
        if hasattr(cap, 'physics_engine') and cap.physics_engine:
             cap.add_ball(pos=(300, 320))
             print("Added Test Ball above Bumper")
    
        # 3. Simulate Game
        max_frames = 500 # Short run, should score quickly
        frames_run = 0
        random.seed(42)
    
        while frames_run < max_frames:
            # Deterministic input pattern
            t = frames_run
            
            # Flippers just in case
            if t % 60 == 10: cap.trigger_left()
            if t % 60 == 40: cap.release_left()
    
            cap.manual_step()
            frames_run += 1
    
            # Debug
            if t % 50 == 0:
                 if cap.physics_engine and float(len(cap.physics_engine.balls)) > 0:
                     b = cap.physics_engine.balls[-1] # Check the last added ball (test ball)
                     print(f"Frame {t}: Score: {cap.score}, Ball Pos: ({b.position.x:.1f}, {b.position.y:.1f})")
                 else:
                     print(f"Frame {t}: Score: {cap.score}, No balls")

            # Stop if we score
            if cap.score > 0:
                # Run a few more frames to settle
                for _ in range(20): 
                    cap.manual_step()
                    frames_run += 1
                break
    
        original_score = cap.score
        print(f"Original Game Finished. Score: {original_score} (Frames: {frames_run})")
        
        # Ensure we actually tested something
        self.assertGreater(original_score, 0, "Original game failed to score > 0, invalid test")
        
        # 4. Extract Replay Data
        # We need to manually construct what save_replay would produce or use the internal data
        replay_data = cap.replay_manager.replay_data.copy()
        
        # Ensure seed is recorded
        print(f"Replay Data Seed: {replay_data.get('seed')}")
        print(f"Replay Data Hashes: Layout={replay_data.get('layout_hash')}, Config={replay_data.get('config_hash')}")
        print(f"Replay Events: {len(replay_data.get('events', []))}")
        
        self.assertIsNotNone(replay_data.get('layout_hash'), "Layout hash not recorded")
        self.assertIsNotNone(replay_data.get('config_hash'), "Config hash not recorded")
        
        # 5. Load Replay
        print("Loading Replay...")
        success = cap.handle_load_replay(replay_data)
        self.assertTrue(success, "Failed to load replay")
        
        self.assertTrue(cap.replay_manager.is_playing, "Replay should be playing after load")
        
        # 6. Run Replay
        # We run for the same number of frames
        print("Running Replay...")
        replay_score = 0
        
        for i in range(frames_run):
            cap.manual_step()
            replay_score = cap.score
            
        print(f"Replay Finished. Score: {replay_score}")
        
        # 7. Compare Scores
        self.assertEqual(original_score, replay_score, 
                         f"Replay score ({replay_score}) does not match original score ({original_score})")

if __name__ == '__main__':
    unittest.main()
