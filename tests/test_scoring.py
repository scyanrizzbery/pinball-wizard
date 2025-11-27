import time
import numpy as np
import sys
import os
import random

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from pbwizard.vision import SimulatedFrameCapture, PinballLayout

def test_scoring():
    print("Initializing Simulation...")
    sim = SimulatedFrameCapture(width=450, height=800, headless=True)
    sim.start()
    sim.launch_ball()
    
    total_score = 0
    max_steps = 1000
    
    print("Running random actions...")
    for i in range(max_steps):
        # Randomly flip
        if random.random() < 0.1:
            sim.trigger_left()
        elif random.random() < 0.1:
            sim.release_left()
            
        if random.random() < 0.1:
            sim.trigger_right()
        elif random.random() < 0.1:
            sim.release_right()
            
        # Check score
        if sim.score > total_score:
            print(f"Step {i}: Score increased! {total_score} -> {sim.score}")
            total_score = sim.score
            
        time.sleep(0.01)
        
        # Respawn if lost
        if not sim.balls:
            sim.launch_ball()
            
    print(f"Final Score: {total_score}")
    
    sim.stop()
    
    if total_score > 0:
        print("SUCCESS: Scoring is possible.")
    else:
        print("FAILURE: No score achieved with random actions.")

if __name__ == "__main__":
    test_scoring()
