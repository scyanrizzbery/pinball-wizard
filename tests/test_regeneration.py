
import logging
import time
import sys
import unittest
from pbwizard.physics import Physics, PymunkEngine
from pbwizard.config import PhysicsConfig

# Mock classes
class MockLayout:
    def __init__(self):
        self.bumpers = [
            {'x': 0.5, 'y': 0.5},
            {'x': 0.3, 'y': 0.3}
        ]
        self.drop_targets = []
        self.name = 'test'
        self.left_flipper_x_min = 0.1
        self.left_flipper_y_max = 0.9
        self.right_flipper_x_max = 0.9
        self.right_flipper_y_max = 0.9
        self.rails = []

class TestBumperLogic(unittest.TestCase):
    def setUp(self):
        self.config = PhysicsConfig()
        self.config.bumper_respawn_time = 0.5 # Fast for testing
        self.layout = MockLayout()
        self.engine = PymunkEngine(self.layout, 1000, 1000, config=self.config)
        
        # Override spawn_mothership
        self.engine.spawn_mothership = self.mock_spawn_mothership
        self.mothership_spawned = False
        
    def mock_spawn_mothership(self):
        self.mothership_spawned = True
        self.engine.mothership_active = True

    def test_mothership_pauses_regeneration(self):
        print("\n--- Testing Mothership Pauses Regeneration ---")
        
        # 1. Destroy Both Bumpers to Spawn Mothership
        for bumper_shape in list(self.engine.bumper_shape_map.keys()):
            idx = self.engine.bumper_shape_map[bumper_shape]
            self.engine.bumper_health[idx] = 0
            self.engine.bumper_respawn_timers[idx] = self.config.bumper_respawn_time
            self.engine.space.remove(bumper_shape)
            
        # Trigger update to spawn
        self.engine.update(0.1)
        self.assertTrue(self.mothership_spawned, "Mothership should have spawned")
        
        # 2. Advance Time well past respawn time
        self.engine.update(2.0) # Should be ample time (0.5s respawn)
        
        # 3. Verify Bumpers have NOT regenerated
        active = 0
        for t in self.engine.bumper_respawn_timers:
            if t <= 0: active += 1
            
        self.assertEqual(active, 0, "Bumpers should NOT regenerate while Mothership matches")
        print("Bumpers correctly stayed dead while Mothership active.")
        
        # 4. Kill Mothership
        self.engine.mothership_active = False
        
        # 5. Advance Time
        self.engine.update(0.6)
        
        # 6. Verify Regeneration
        active = 0
        for t in self.engine.bumper_respawn_timers:
            if t <= 0: active += 1
            
        self.assertEqual(active, 2, "Bumpers should regenerate after Mothership gone")
        print("Bumpers regenerated after Mothership defeated.")

if __name__ == '__main__':
    unittest.main()
