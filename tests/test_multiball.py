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
        # Sim does not accept headless arg, reads from env
        self.sim = SimulatedFrameCapture(width=450, height=800)
        self.sim.start()
        
        # Wait for auto-start (due to 1s delay)
        start_time = time.time()
        while len(self.sim.balls) == 0:
            if time.time() - start_time > 2.0:
                break
            time.sleep(0.1)
            
        # Ensure exactly one ball
        if len(self.sim.balls) > 1:
            # Remove extras
            self.sim.balls = self.sim.balls[:1]
            # Also fix physics engine? 
            # It's hard to sync physics engine removal.
            # Let's just accept >= 1 and use the first ball.
            pass

    def tearDown(self):
        self.sim.stop()

    def test_multiball_activation(self):
        print(f"Initial balls: {len(self.sim.balls)}")
        self.assertGreaterEqual(len(self.sim.balls), 1)
        
        # Manually trigger all drop targets
        print("Triggering drop targets...")
        with self.sim.lock:
            self.sim.drop_target_states = [False] * len(self.sim.layout.drop_targets)
            
            # Reset one target to True so we can hit it
            self.sim.drop_target_states[0] = True
            
            # Move ball to target 0
            target = self.sim.layout.drop_targets[0]
            
            # Place ball below target (higher Y) and shoot it up
            # Place ball below target (higher Y) and shoot it up
            # We must update the PHYSICS BODY, not just the visual ball dict
            body = self.sim.physics_engine.balls[0]
            start_x = target['x'] * self.sim.width
            start_y = (target['y'] + 0.05) * self.sim.height
            body.position = (start_x, start_y)
            body.velocity = (0, -1000) # Shoot up FAST (pixels/sec)
            
            # Also update visual for consistency (though it will be overwritten)
            self.sim.balls[0]['pos'] = np.array([start_x, start_y])
            self.sim.balls[0]['vel'] = np.array([0, -1000], dtype=float)
            print(f"Set velocity to: {body.velocity}")
            
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
