import unittest
import numpy as np
from pbwizard.vision import SimulatedFrameCapture
from pbwizard.config import PhysicsConfig

class TestGravity(unittest.TestCase):
    def test_gravity_update(self):
        """Test that changing table_tilt updates physics engine gravity correctly."""
        # Initialize with known defaults
        sim = SimulatedFrameCapture(width=400, height=800)
        # Ensure physics engine is real
        self.assertIsNotNone(sim.physics_engine)
        
        # Default config
        base_tilt = 8.5
        base_mag = 9000.0
        expected_y = base_mag * np.sin(np.radians(base_tilt))
        
        # Explicitly set params to ensure known state (overriding any layout defaults)
        sim.update_physics_params({'gravity_magnitude': 9000.0, 'table_tilt': 8.5})
        
        gx, gy = sim.physics_engine.space.gravity
        print(f"Initial Gravity: ({gx}, {gy})")
        
        self.assertAlmostEqual(gx, 0.0)
        self.assertAlmostEqual(gy, expected_y, places=1)
        
        # Change tilt to 15 degrees
        new_tilt = 15.0
        sim.update_physics_params({'table_tilt': new_tilt})
        
        expected_new_y = base_mag * np.sin(np.radians(new_tilt))
        gx_new, gy_new = sim.physics_engine.space.gravity
        print(f"New Gravity (15deg): ({gx_new}, {gy_new})")
        
        self.assertAlmostEqual(gx_new, 0.0)
        self.assertAlmostEqual(gy_new, expected_new_y, places=1)
        self.assertNotEqual(gy, gy_new)
        
    def test_gravity_magnitude_update(self):
        """Test that changing gravity_magnitude updates physics engine gravity correctly."""
        sim = SimulatedFrameCapture(width=400, height=800)
        
        current_tilt = sim.physics_engine.config.table_tilt
        new_mag = 5000.0
        
        sim.update_physics_params({'gravity_magnitude': new_mag})
        
        expected_y = new_mag * np.sin(np.radians(current_tilt))
        gx, gy = sim.physics_engine.space.gravity
        
        self.assertAlmostEqual(gy, expected_y, places=1)

if __name__ == '__main__':
    unittest.main()
