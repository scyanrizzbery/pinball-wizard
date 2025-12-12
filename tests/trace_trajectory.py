
import logging
import os
import time
import numpy as np
from pbwizard import vision

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("trace_trajectory")

def trace():
    logger.info("Starting Trajectory Trace")
    
    # Setup Threaded (Default)
    if 'HEADLESS_SIM' in os.environ:
        del os.environ['HEADLESS_SIM']
    
    cap = vision.SimulatedFrameCapture(width=450, height=800)
    
    # Ensure auto-plunge is ON (simulating our fix)
    if cap.physics_engine:
        cap.physics_engine.config.auto_plunge_enabled = True
        
    cap.start()
    time.sleep(1) # Wait for init
    
    # Run 20 Episodes
    drain_positions = []
    
    for ep in range(20):
        # Reset via Physics Engine directly? 
        # In threaded mode, we should be careful.
        # But let's try just observing the FIRST episode.
        # Resetting might be tricky if thread is running.
        if ep > 0:
             cap.physics_engine.reset_game()
             # Re-force flag
             if cap.physics_engine: cap.physics_engine.config.auto_plunge_enabled = True
             time.sleep(0.5)

        ep_positions = []
        drained = False
        start_time = time.time()
        
        # Monitor for 8 seconds (approx 500 steps)
        while time.time() - start_time < 8.0:
            time.sleep(0.016) # ~60Hz poll
            
            status = cap.get_ball_status()
            if status:
                pos, _ = status
                ep_positions.append(pos)
                
                # Check Drain
                if pos[1] > 780:
                    logger.info(f"Ep {ep}: Drained at x={pos[0]:.1f}, y={pos[1]:.1f}")
                    drain_positions.append(pos[0])
                    drained = True
                    break
        
        if not drained:
             logger.info(f"Ep {ep}: Survived 8s (buffer len {len(ep_positions)})")
            
        if not drained:
            logger.info(f"Ep {ep}: Buttoned up / Stuck (Steps {len(ep_positions)})")

    # Stats
    if drain_positions:
        avg_drain_x = np.mean(drain_positions)
        logger.info(f"Average Drain X: {avg_drain_x:.1f}")
        logger.info(f"Drain X Distribution: {drain_positions}")
    else:
        logger.info("No drains recorded!")
        
    cap.stop()

if __name__ == "__main__":
    trace()
