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

if __name__ == "__main__":
    unittest.main()
