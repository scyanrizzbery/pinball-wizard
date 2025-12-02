import unittest
import numpy as np
from pbwizard.vision import ZoneManager, SimulatedFrameCapture

class TestVision(unittest.TestCase):
    def test_zone_manager_boundaries(self):
        width, height = 1000, 1000
        zm = ZoneManager(width, height)
        
        # Manually set contours for testing since ZoneManager initializes them from layout
        # Left Zone: 200-400 width, 750-950 height
        left_cnt = np.array([[200, 750], [400, 750], [400, 950], [200, 950]])
        # Right Zone: 600-800 width, 750-950 height
        right_cnt = np.array([[600, 750], [800, 750], [800, 950], [600, 950]])
        
        zm.set_contours([
            {'type': 'left', 'cnt': left_cnt},
            {'type': 'right', 'cnt': right_cnt}
        ])
        
        # Check Left Zone
        # Inside
        status = zm.get_zone_status(300, 800)
        self.assertTrue(status['left'])
        self.assertFalse(status['right'])
        
        # Outside X
        status = zm.get_zone_status(100, 800)
        self.assertFalse(status['left'])
        
        status = zm.get_zone_status(500, 800)
        self.assertFalse(status['left'])
        
        # Outside Y
        status = zm.get_zone_status(300, 700)
        self.assertFalse(status['left'])
        
        status = zm.get_zone_status(300, 1100)
        self.assertFalse(status['left'])

        # Check Right Zone
        # Inside
        status = zm.get_zone_status(700, 800)
        self.assertTrue(status['right'])
        self.assertFalse(status['left'])
        
        # Outside
        status = zm.get_zone_status(500, 800)
        self.assertFalse(status['right'])

    def test_flipper_line_calculation(self):
        sim = SimulatedFrameCapture(width=100, height=100)
        
        # Test Left Flipper Line Calculation
        # Rect: (20, 75, 40, 85) -> Width=20
        # Pivot: Bottom-Left (20, 85)
        rect = (20, 75, 40, 85)
        
        # Angle 0 (Horizontal)
        p1, p2 = sim._get_flipper_line_from_angle(rect, 0, 'left')
        np.testing.assert_allclose(p1, [20, 85])
        # Length 20, Angle 0 -> x+20, y-0
        np.testing.assert_allclose(p2, [40, 85])
        
        # Angle -90 (Vertical Up)
        p1, p2 = sim._get_flipper_line_from_angle(rect, -90, 'left')
        # Length 20, Angle -90 -> x+0, y-20
        np.testing.assert_allclose(p2, [20, 65])

    def test_symmetric_flipper_angles(self):
        sim = SimulatedFrameCapture(width=100, height=100)
        
        # Default: Resting -30, Stroke 50
        # Left Down: -30
        # Right Down: 180 - (-30) = 210
        
        sim._update_flipper_angles(0.1) # Initialize/Update
        
        # Force angles to resting
        sim.current_left_angle = -30
        sim.current_right_angle = 210
        
        # Change resting angle to -45
        sim.update_physics_params({'flipper_resting_angle': -45})
        
        self.assertEqual(sim.flipper_resting_angle, -45)
        
        # Run update loop for a bit to let angles settle
        for _ in range(100):
            sim._update_flipper_angles(0.1)
            
        # Left should settle at -45
        np.testing.assert_allclose(sim.current_left_angle, -45, atol=1.0)
        
        # Right should settle at 180 - (-45) = 225
        np.testing.assert_allclose(sim.current_right_angle, 225, atol=1.0)

    def test_collision_detection_static(self):
        sim = SimulatedFrameCapture(width=100, height=100)
        sim.ball_radius = 5
        
        # Ball at (50, 50)
        ball = {
            'pos': np.array([50.0, 50.0]),
            'vel': np.array([0.0, 0.0]),
            'lost': False
        }
        sim.balls = [ball]
        
        # Line passing through ball (40, 50) to (60, 50)
        p1 = np.array([40.0, 50.0])
        p2 = np.array([60.0, 50.0])
        
        # Should detect collision
        sim._check_line_collision(ball, p1, p2, active=False)
        
        # Ball should be pushed out (radius 5)
        self.assertFalse(np.allclose(ball['pos'], [50.0, 50.0]))

    def test_collision_detection_thickness(self):
        sim = SimulatedFrameCapture(width=100, height=100)
        sim.ball_radius = 5
        
        # Ball at (50, 40)
        ball = {
            'pos': np.array([50.0, 40.0]),
            'vel': np.array([0.0, 0.0]),
            'lost': False
        }
        sim.balls = [ball]
        
        # Line at y=50 (Horizontal)
        p1 = np.array([0.0, 50.0])
        p2 = np.array([100.0, 50.0])
        
        # Distance is 10. Radius is 5. No collision normally.
        sim._check_line_collision(ball, p1, p2, active=False, thickness=0)
        np.testing.assert_allclose(ball['pos'], [50.0, 40.0])
        
        # With thickness 15 (effective radius = 5 + 7.5 = 12.5)
        # Distance 10 < 12.5 -> Collision!
        sim._check_line_collision(ball, p1, p2, active=False, thickness=15)
        self.assertFalse(np.allclose(ball['pos'], [50.0, 40.0]))

    def test_3d_projection(self):
        width, height = 600, 800
        sim = SimulatedFrameCapture(width=width, height=height)
        
        # Test Center Projection with Top-Down Camera
        # Position camera directly above center
        sim.cam_x = width / 2
        sim.cam_y = height / 2
        sim.cam_z = 1000
        sim.pitch = 0 # Looking straight down (assuming 0 is down-ish or we align ry/rz)
        # Wait, if pitch=0: cy = ry, cz = rz.
        # ry = y - cam_y = 0. rz = z - cam_z = -1000.
        # cy = 0. cz = -1000.
        # sy = 0 + height/2. Correct.
        
        # Center of table (width/2, height/2, 0) should project roughly to center of screen
        sx, sy = sim._project_3d(width/2, height/2, 0)
        
        # Should be close to screen center (width/2, height/2)
        self.assertTrue(abs(sx - width/2) < 20)
        self.assertTrue(abs(sy - height/2) < 20)
        
        # Test Top vs Bottom
        # Top (y=0) should be HIGHER on screen (smaller sy) than Bottom (y=height)
        _, sy_top = sim._project_3d(width/2, 0, 0)
        _, sy_bottom = sim._project_3d(width/2, height, 0)
        
        self.assertLess(sy_top, sy_bottom)

    def test_draw_frame_3d(self):
        sim = SimulatedFrameCapture(width=100, height=100)
        # Add a ball
        sim.balls.append({
            'pos': np.array([50.0, 50.0]),
            'vel': np.array([0.0, 0.0]),
            'lost': False
        })
        
        # Should run without error
        sim._draw_frame()
        
        self.assertIsNotNone(sim.frame)
        self.assertEqual(sim.frame.shape, (100, 100, 3))

if __name__ == "__main__":
    unittest.main()
