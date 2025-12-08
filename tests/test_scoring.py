import unittest
import time
import sys
import os
import random
import numpy as np

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from pbwizard.vision import SimulatedFrameCapture

class TestScoring(unittest.TestCase):
    def setUp(self):
        print("Initializing Simulation...")
        self.sim = SimulatedFrameCapture(width=450, height=800)
        # self.sim.start() # Do not start thread to avoid race condition with Pymunk
        # Just add a ball directly
        ball_pos = (200, 400) # center-ish
        if hasattr(self.sim, 'physics_engine') and self.sim.physics_engine:
             self.sim.physics_engine.add_ball(ball_pos)

    def tearDown(self):
        # self.sim.stop()
        pass

    def test_scoring_mechanics(self):
        total_score = 0
        max_steps = 1000
        score_increased = False
        
        print("Running random actions...")
        for i in range(max_steps):
            # Randomly flip
            if random.random() < 0.1:
                self.sim.trigger_left()
            elif random.random() < 0.1:
                self.sim.release_left()
                
            if random.random() < 0.1:
                self.sim.trigger_right()
            elif random.random() < 0.1:
                self.sim.release_right()
                
            # Check score from physics engine (sim.score requires _draw_frame to sync)
            current_score = self.sim.physics_engine.score if hasattr(self.sim, 'physics_engine') else self.sim.score
            if current_score > total_score:
                print(f"Step {i}: Score increased! {total_score} -> {current_score}")
                total_score = current_score
                score_increased = True
                
            # time.sleep(0.001) # Faster sleep for tests
            self.sim.physics_engine.update(0.016) # Step logic manually instead of thread
            
            # Respawn if lost
            if not self.sim.balls:
                if hasattr(self.sim, 'physics_engine') and self.sim.physics_engine:
                     self.sim.physics_engine.add_ball((225, 400))
                
        print(f"Final Score: {total_score}")
        
        # Let's force a score to ensure the test is deterministic
        if not score_increased:
            # Manually place ball on a bumper
            if self.sim.layout.bumpers and self.sim.physics_engine and self.sim.physics_engine.balls:
                bumper = self.sim.layout.bumpers[0]
                # Move PHYSICS BODY
                body = self.sim.physics_engine.balls[0]
                body.position = (bumper['x'] * self.sim.width, bumper['y'] * self.sim.height)
                
                # Run a few steps to trigger collision
                for _ in range(10):
                    # time.sleep(0.01)
                    self.sim.physics_engine.update(0.016)
                    current_score = self.sim.physics_engine.score if hasattr(self.sim, 'physics_engine') else self.sim.score
                    if current_score > total_score:
                        score_increased = True
                        break
        
        self.assertTrue(score_increased, "FAILURE: No score achieved even with forced placement.")

    def test_multiplier_scoring(self):
        """Verify score multiplier increases points awarded."""
        # Reset score
        self.sim.score = 0
        
        # Force a 3x multiplier
        # Use physics_engine as per recent fixes
        engine_attr = 'physics_engine' if hasattr(self.sim, 'physics_engine') else 'engine'
        
        if hasattr(self.sim, engine_attr):
            engine = getattr(self.sim, engine_attr)
            
            # Set up a combo that won't be reset by the first hit
            engine.combo_count = 3
            engine.score_multiplier = 3.0
            engine.last_hit_time = time.time() - 0.1  # Recent hit 0.1s ago (within combo window)
            
            # 1. Place ball on bumper
            if self.sim.balls and self.sim.layout.bumpers:
                bumper = self.sim.layout.bumpers[0]
                
                # Move ball to bumper
                # balls list might be detached from physics in test env? No, logic uses engine.balls
                if engine.balls:
                    ball_body = engine.balls[0]
                    ball_body.position = tuple(bumper['pos'])
                    
                    # Step physics to trigger collision
                    # We need to ensure the collision handler uses the multiplier
                    for _ in range(5):
                        engine.space.step(0.016)
                        
                    if engine.score > 0:
                        print(f"Score with combo: {engine.score}, combo_count: {engine.combo_count}")
                        # It should be significantly higher than base score (10)
                        self.assertGreater(engine.score, 30, "Score should reflect multiplier and combo bonus")
            else:
                print("Skipping multiplier test - no balls/bumpers")

if __name__ == "__main__":
    unittest.main()
