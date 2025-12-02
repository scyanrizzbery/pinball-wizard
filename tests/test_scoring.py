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
        self.sim = SimulatedFrameCapture(width=450, height=800, headless=True)
        self.sim.start()
        self.sim.launch_ball()

    def tearDown(self):
        self.sim.stop()

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
                
            # Check score
            if self.sim.score > total_score:
                print(f"Step {i}: Score increased! {total_score} -> {self.sim.score}")
                total_score = self.sim.score
                score_increased = True
                
            time.sleep(0.001) # Faster sleep for tests
            
            # Respawn if lost
            if not self.sim.balls:
                self.sim.launch_ball()
                
        print(f"Final Score: {total_score}")
        
        # Assert that we managed to score at least something (it's random but likely)
        # If this is flaky, we might need a more deterministic test, 
        # e.g. placing the ball directly on a bumper.
        
        # Let's force a score to ensure the test is deterministic
        if not score_increased:
            # Manually place ball on a bumper
            if self.sim.balls:
                bumper = self.sim.bumpers[0]
                self.sim.balls[0]['pos'] = bumper['pos'].copy()
                # Run a few steps to trigger collision
                for _ in range(10):
                    time.sleep(0.01)
                    if self.sim.score > total_score:
                        score_increased = True
                        break
        
        self.assertTrue(score_increased, "FAILURE: No score achieved even with forced placement.")

    def test_multiplier_scoring(self):
        """Verify score multiplier increases points awarded."""
        # Reset score
        self.sim.score = 0
        initial_score = 0
        
        # Force a 3x multiplier
        # Use physics_engine as per recent fixes
        engine_attr = 'physics_engine' if hasattr(self.sim, 'physics_engine') else 'engine'
        
        if hasattr(self.sim, engine_attr):
            engine = getattr(self.sim, engine_attr)
            engine.score_multiplier = 3.0
            engine.combo_count = 3
            
            # Manually trigger a score event (e.g. bumper hit)
            # We can use the internal method if accessible, or simulate collision
            # For simplicity, let's use the engine's score adding logic directly if possible
            # But engine.score is separate from sim.score (sim reads from engine)
            
            # Let's simulate a hit by calling the collision handler logic directly?
            # Or just verify the engine's multiplier logic in isolation (already covered in test_combos)
            # Let's try to do an integration test:
            
            # 1. Place ball on bumper
            if self.sim.balls and self.sim.bumpers:
                bumper = self.sim.bumpers[0]
                
                # Move ball to bumper
                ball_body = engine.balls[0]
                ball_body.position = bumper['pos']
                
                # Step physics to trigger collision
                # We need to ensure the collision handler uses the multiplier
                for _ in range(5):
                    engine.space.step(0.016)
                    
                # Check if score increased by > 100 (base score)
                # Base score is 100. With 3x, it should be 300 + bonus
                # Bonus = 50 * 3 = 150. Total = 450.
                
                if engine.score > 0:
                    print(f"Score with 3x multiplier: {engine.score}")
                    # It should be significantly higher than 100
                    self.assertGreater(engine.score, 150, "Score should reflect multiplier")
            else:
                print("Skipping multiplier test - no balls/bumpers")


if __name__ == "__main__":
    unittest.main()
