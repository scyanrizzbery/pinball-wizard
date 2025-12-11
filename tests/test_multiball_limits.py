import unittest
from pbwizard.vision import SimulatedFrameCapture, PinballLayout

class TestMultiballLimits(unittest.TestCase):
    def test_max_balls(self):
        """Test that multiball respects the 5-ball limit."""
        # Setup layout with drop targets (needed for logic init, though we'll cheat)
        layout_config = {
            'drop_targets': [{'x': 0.5, 'y': 0.5, 'width': 0.1, 'height': 0.05}]
        }
        sim = SimulatedFrameCapture(width=400, height=800, layout_config=layout_config)
        engine = sim.physics_engine
        
        # Manually add balls up to limit
        # Start with 1 (default?) - assuming init creates none or 1? checking balls list
        engine.balls = [] # Clear
        for _ in range(5):
             engine.add_ball((100, 100))
             engine.space.step(0.016) # Process callbacks
        
        self.assertEqual(len(engine.balls), 5)
        
        # Trigger Multiball Logic
        # We need to simulate the condition: all drop targets hit -> add_ball
        # We can bypass the collision handler by reusing the logic logic block?
        # Or better, just check the logic in a mock way or trigger the collision?
        
        # For simplicity, let's just inspect the line we changed? 
        # No, let's run the code. We can manually call 'reset_drop_targets' 
        # but the trigger is inside 'begin_collision'.
        # We CANNOT easily invoke begin_collision from outside without colliding things.
        
        # However, we can create a situation where a collision MUST happen.
        # But pymunk is non-deterministic or hard to frame-perfect.
        
        # Alternative: We can verify the logic by reading the source or trusting the manual change?
        # NO, we should test.
        
        # Let's verify by manually calling the logic block if we extract it?
        # Too invasive.
        
        # Let's try to trigger it via collision.
        # 1. Place ball exactly on drop target.
        # 2. Step physics.
        # 3. Check ball count.
        
        # Reset engine with 4 balls
        engine.balls = []
        for i in range(4):
             engine.add_ball((50 + i * 30, 50)) # Spread out to prevent explosion
             engine.space.step(0.016)
             
        # Target at 0.5, 0.5 (200, 400)
        # Drop target logic only triggers if it was the last one.
        # Our layout has 1 target. So hitting it clears the bank.
        
        # Place 5th ball ON colliding path with target
        # Target center: 200, 400. Size: 40x40 (0.1*400, 0.05*800)
        # Ball at 200, 400
        engine.add_ball((200, 400))
        # Now 5 balls.
        
        # Step
        engine.space.step(0.1)
        
        # Should have triggered multiball.
        # But we are AT 5 balls (4 + collider).
        # So it should NOT add a 6th.
        
        # Wait, if loop is: collision -> drop target update -> check all down -> add ball
        # Yes.
        
        self.assertEqual(len(engine.balls), 5, "Should not exceed 5 balls")
        
        # Now try with 3 balls (total 4 after add)
        engine.balls = []
        engine.drop_target_states = [True] # Reset target
        engine.drop_target_shapes = [] # Clear old shapes from engine list, not space?
        # Re-init targets to be safe
        engine.reset_drop_targets()
        
        for _ in range(3):
             engine.add_ball((50, 50))
             
        # Add collider (4th ball)
        engine.add_ball((200, 400))
        
        step_count = 0
        while step_count < 10:
            engine.space.step(0.016)
            step_count += 1
            if not all(engine.drop_target_states):
                break
        
        # Should have triggered multiball (added 1) -> Total 5
        # If it worked, len is 5.
        
        # Note: Collision might throw the ball away, but ball count remains unless lost.
        self.assertEqual(len(engine.balls), 5, "Should have added 5th ball")

if __name__ == '__main__':
    unittest.main()
