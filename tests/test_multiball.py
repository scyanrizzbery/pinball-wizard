import time
import numpy as np
import sys
import os

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from pbwizard.vision import SimulatedFrameCapture, PinballLayout

def test_multiball():
    print("Initializing Simulation...")
    sim = SimulatedFrameCapture(width=450, height=800, headless=True)
    sim.start()
    sim.launch_ball()
    
    print(f"Initial balls: {len(sim.balls)}")
    assert len(sim.balls) == 1
    
    # Manually trigger all drop targets
    print("Triggering drop targets...")
    with sim.lock:
        sim.drop_target_states = [False] * len(sim.layout.drop_targets)
        # Force a check by simulating a collision with the last target
        # We need to manually call _check_drop_target_collision or just wait for the loop
        # But since we set states to False, the loop won't trigger the "hit" logic which adds the ball
        # So we need to simulate the hit event logic manually or cheat
        
        # Let's cheat and call add_ball directly to verify it works, 
        # but ideally we want to test the trigger logic.
        
        # Reset one target to True so we can hit it
        sim.drop_target_states[0] = True
        
        # Move ball to target 0
        target = sim.layout.drop_targets[0]
        # Place ball slightly below target to ensure collision when moving up?
        # Or just place it exactly on target as before.
        # The issue might be that the ball is lost because it moved out of bounds?
        # Let's verify ball isn't lost first.
        
        # Place ball below target (higher Y) and shoot it up
        sim.balls[0]['pos'] = np.array([target['x'] * sim.width, (target['y'] + 0.05) * sim.height])
        sim.balls[0]['vel'] = np.array([0, -20], dtype=float) # Shoot up FAST
        print(f"Set velocity to: {sim.balls[0]['vel']}")
        
    print("Waiting for physics loop to detect collision...")
    for i in range(20):
        time.sleep(0.05)
        if sim.balls:
            print(f"Frame {i}: Balls={len(sim.balls)} Pos={sim.balls[0]['pos']}, Vel={sim.balls[0]['vel']}")
    
    print(f"Balls after collision: {len(sim.balls)}")
    if len(sim.balls) > 1:
        print("SUCCESS: Multiball activated!")
    else:
        print("FAILURE: Multiball not activated.")
        # Debug info
        print(f"Drop target states: {sim.drop_target_states}")
        print(f"Ball pos: {sim.balls[0]['pos']}")
        
    sim.stop()

if __name__ == "__main__":
    test_multiball()
