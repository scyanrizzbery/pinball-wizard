import unittest
from pbwizard.vision import SimulatedFrameCapture
from pbwizard.config import PhysicsConfig

class TestPhysicsParamsUpdate(unittest.TestCase):
    def test_materials_update(self):
        """Test that updating friction/restitution updates ball shapes."""
        sim = SimulatedFrameCapture(width=400, height=800)
        
        # Add a ball manually to test updates
        sim.physics_engine.add_ball((100, 100))
        ball = sim.physics_engine.balls[0]
        ball_shape = list(ball.shapes)[0]
        
        # Initial defaults (elasticity uses restitution default of 0.5)
        self.assertAlmostEqual(ball_shape.friction, 0.01)
        self.assertAlmostEqual(ball_shape.elasticity, 0.5)
        
        # Update params
        new_params = {
            'friction': 0.01,
            'restitution': 0.9,
            'ball_mass': 5.0
        }
        sim.update_physics_params(new_params)
        
        # Check if updated on existing ball
        self.assertAlmostEqual(ball_shape.friction, 0.01)
        self.assertAlmostEqual(ball_shape.elasticity, 0.9)
        self.assertAlmostEqual(ball.mass, 5.0)
        
    def test_config_propogation(self):
        """Test that vision.py propagates params to config correctly."""
        sim = SimulatedFrameCapture(width=400, height=800)
        
        params = {'gravity_magnitude': 1234.0, 'table_tilt': 10.0}
        sim.update_physics_params(params)
        
        self.assertEqual(sim.physics_engine.config.gravity_magnitude, 1234.0)
        self.assertEqual(sim.physics_engine.config.table_tilt, 10.0)

if __name__ == '__main__':
    unittest.main()
