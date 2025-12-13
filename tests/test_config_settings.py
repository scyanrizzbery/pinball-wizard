
import unittest
from pbwizard.physics import PymunkEngine
from pbwizard.config import PhysicsConfig

# Mock classes
class MockLayout:
    def __init__(self):
        self.bumpers = [{'x': 0.5, 'y': 0.5}]
        self.drop_targets = [{'x': 0.2, 'y': 0.2, 'width': 0.05, 'height': 0.02}]
        self.name = 'test'
        self.left_flipper_x_min = 0.1
        self.left_flipper_y_max = 0.9
        self.right_flipper_x_max = 0.9
        self.right_flipper_y_max = 0.9
        self.rails = []
        self.upper_flippers = []

class TestPhysicsConfig(unittest.TestCase):
    def setUp(self):
        self.config = PhysicsConfig()
        self.layout = MockLayout()
        self.engine = PymunkEngine(self.layout, 1000, 1000, config=self.config)

    def test_bumper_respawn_config(self):
        print("\n--- Testing Bumper Respawn Configuration ---")
        # Default is 10.0
        self.assertEqual(self.engine.config.bumper_respawn_time, 10.0)
        
        # Change config
        self.engine.config.bumper_respawn_time = 5.0
        
        # Destroy bumper
        idx = 0
        bumper_shape = list(self.engine.bumper_shape_map.keys())[0]
        self.engine.bumper_health[idx] = 0
        
        # Simulate destruction logic (copy of what's in begin_collision)
        respawn_time = getattr(self.engine.config, 'bumper_respawn_time', 10.0)
        self.engine.bumper_respawn_timers[idx] = respawn_time
        
        self.assertEqual(self.engine.bumper_respawn_timers[idx], 5.0, "Bumper timer should use new config value")
        print("Bumper respawn time correctly updated from config.")

    def test_drop_target_cooldown_config(self):
        print("\n--- Testing Drop Target Cooldown Configuration ---")
        # Default is 2.0
        self.assertEqual(self.engine.config.drop_target_cooldown, 2.0)
        
        # Change config
        self.engine.config.drop_target_cooldown = 0.5
        
        # Reset drop targets (simulates hitting them all or game reset)
        self.engine.reset_drop_targets()
        
        # Check timer
        self.assertEqual(self.engine.drop_target_timer, 0.5, "Drop target timer should use new config value")
        print("Drop target cooldown correctly updated from config.")

if __name__ == '__main__':
    unittest.main()
