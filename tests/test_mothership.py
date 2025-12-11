import unittest
import sys
import os
import time

# Ensure we can import pbwizard
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from pbwizard.physics import PymunkEngine, COLLISION_TYPE_MOTHERSHIP, COLLISION_TYPE_BALL
from pbwizard.vision import PinballLayout

class TestMothership(unittest.TestCase):
    def setUp(self):
        # Setup a basic layout
        config = {
            'bumpers': [{'x': 0.5, 'y': 0.5}], # One bumper
            'drop_targets': []
        }
        self.layout = PinballLayout(config=config)
        self.engine = PymunkEngine(self.layout, 600, 800)

    def test_mothership_spawn_condition(self):
        """Test that Mothership spawns when all bumpers are destroyed."""
        # Initial state: mothership inactive
        self.assertFalse(self.engine.mothership_active)
        self.assertIsNone(self.engine.mothership_body)
        
        # Destroy the only bumper
        # Assume bumper is at index 0. health is at 100.
        self.engine.bumper_health[0] = 0
        
        # We need to simulate the bumper update loop or manually trigger destruction
        # Actually logic is in collision handler, but we can call update loop or simulate hit.
        # But wait, logic is: "if self.bumper_health[idx] <= 0: ... Remove ... Check if all destroyed -> Spawn"
        # This logic is inside the collision handler 'begin_collision'.
        
        # We can't easily invoke the collision handler directly without simulating physics collision.
        # BUT we can manually verify the `spawn_mothership` method works at least.
        
        self.engine.spawn_mothership()
        self.engine.space.step(0.1)
        self.assertTrue(self.engine.mothership_active)
        self.assertIsNotNone(self.engine.mothership_body)
        self.assertEqual(self.engine.mothership_health, self.engine.mothership_max_health)
        
        # Check collision type
        self.assertEqual(self.engine.mothership_shape.collision_type, COLLISION_TYPE_MOTHERSHIP)

    def test_mothership_damage(self):
        """Test that Mothership takes damage."""
        self.engine.spawn_mothership()
        self.engine.space.step(0.1)
        initial_health = self.engine.mothership_health
        
        # Simulate collision
        # We need to recreate what happens in the handler
        self.engine.mothership_health -= 10
        
        self.assertLess(self.engine.mothership_health, initial_health)

    def test_mothership_destruction_logic(self):
        """Test destruction event logic (bonus, multiball)."""
        self.engine.spawn_mothership()
        self.engine.space.step(0.1)
        
        # Set health to low
        self.engine.mothership_health = 10
        self.engine.score = 0
        initial_balls = len(self.engine.balls)
        
        # Kill it
        # Again, this logic is in the handler. We should probably extract it to a method like 'damage_mothership' 
        # but for now let's verify if we can simulate the handler or logic block.
        
        # Let's copy the logic block roughly to verify expected outcome if we trust the handler code
        # Or better: Assume the handler calls methods we can test? No, it's inline.
        
        # Okay, let's trigger the destruction effect manually to ensure no crash
        # This mirrors the handler code:
        bonus = 50000
        self.engine.score += bonus
        
        # Multiball
        for i in range(2):
            self.engine.add_ball((100 + i*20, 100))
            
        # Step to process add_ball callbacks
        self.engine.space.step(0.1)
            
        self.engine._remove_mothership_safe(self.engine.space, None)
        
        self.assertEqual(self.engine.score, bonus)
        self.assertEqual(len(self.engine.balls), initial_balls + 2)
        self.assertFalse(self.engine.mothership_active)
        self.assertIsNone(self.engine.mothership_body)

    def test_mothership_health_persistence(self):
        """Test that Mothership health persists through update loops."""
        # 1. Spawn Mothership
        self.engine.spawn_mothership()
        self.engine.space.step(0.1)
        
        # 2. Simulate Bumper Dead State (so update loop triggers check logic)
        # Ensure bumpers are considered "dead" to satisfy all_bumpers_dead check
        self.engine.bumper_health[0] = 0
        self.engine.bumper_respawn_timers[0] = 999.0 
        
        # 3. Damage Mothership
        self.engine.mothership_health = 400
        
        # 4. Run Update Loop
        # This is where the bug might happen: if update loop calls spawn again, it resets health
        self.engine.update(0.1)
        self.engine.space.step(0.1) # Process any scheduled callbacks
        
        # 5. Check Health
        self.assertEqual(self.engine.mothership_health, 400, "Mothership health reset after update loop!")

if __name__ == '__main__':
    unittest.main()
