import unittest
import time
import numpy as np
import sys
import os

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from pbwizard.vision import SimulatedFrameCapture

class TestMultiball(unittest.TestCase):
    def setUp(self):
        print("Initializing Simulation...")
        self.sim = SimulatedFrameCapture(width=450, height=800, headless=True)
        self.sim.start()
        # self.sim.launch_ball() # Removed: start() triggers auto-start which launches a ball

    def tearDown(self):
        self.sim.stop()

    def test_multiball_activation(self):
        print(f"Initial balls: {len(self.sim.balls)}")
        self.assertEqual(len(self.sim.balls), 1)
        
        # Manually trigger all drop targets
        print("Triggering drop targets...")
        with self.sim.lock:
            self.sim.drop_target_states = [False] * len(self.sim.layout.drop_targets)
            
            # Reset one target to True so we can hit it
            self.sim.drop_target_states[0] = True
            
            # Move ball to target 0
            target = self.sim.layout.drop_targets[0]
            
            # Place ball below target (higher Y) and shoot it up
            self.sim.balls[0]['pos'] = np.array([target['x'] * self.sim.width, (target['y'] + 0.05) * self.sim.height])
            self.sim.balls[0]['vel'] = np.array([0, -20], dtype=float) # Shoot up FAST
            print(f"Set velocity to: {self.sim.balls[0]['vel']}")
            
        print("Waiting for physics loop to detect collision...")
        multiball_active = False
        for i in range(20):
            time.sleep(0.05)
            if len(self.sim.balls) > 1:
                multiball_active = True
                break
        
        print(f"Balls after collision: {len(self.sim.balls)}")
        
        # Debug info if failed
        if not multiball_active:
            print(f"Drop target states: {self.sim.drop_target_states}")
            if self.sim.balls:
                print(f"Ball pos: {self.sim.balls[0]['pos']}")
        
        self.assertTrue(multiball_active, "FAILURE: Multiball not activated.")

if __name__ == "__main__":
    unittest.main()
