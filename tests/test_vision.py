import pytest
import numpy as np
from pbwizard.vision import ZoneManager, SimulatedFrameCapture

def test_zone_manager_boundaries():
    width, height = 1000, 1000
    zm = ZoneManager(width, height)
    
    # Check Left Zone (20-40% width, 75-95% height)
    # Inside
    assert zm.is_in_zone(300, 800, zm.left_flipper_zone)
    # Outside X
    assert not zm.is_in_zone(100, 800, zm.left_flipper_zone)
    assert not zm.is_in_zone(500, 800, zm.left_flipper_zone)
    # Outside Y
    assert not zm.is_in_zone(300, 700, zm.left_flipper_zone)
    assert not zm.is_in_zone(300, 1100, zm.left_flipper_zone)

    # Check Right Zone (60-80% width, 75-95% height)
    # Inside
    assert zm.is_in_zone(700, 800, zm.right_flipper_zone)
    # Outside
    assert not zm.is_in_zone(500, 800, zm.right_flipper_zone)

def test_flipper_line_calculation():
    sim = SimulatedFrameCapture(width=100, height=100)
    
    # Test Left Flipper Line Calculation
    # Rect: (20, 75, 40, 85) -> Width=20
    # Pivot: Bottom-Left (20, 85)
    rect = (20, 75, 40, 85)
    
    # Angle 0 (Horizontal)
    p1, p2 = sim._get_flipper_line_from_angle(rect, 0, 'left')
    assert np.allclose(p1, [20, 85])
    # Length 20, Angle 0 -> x+20, y-0
    assert np.allclose(p2, [40, 85])
    
    # Angle 90 (Vertical Up)
    p1, p2 = sim._get_flipper_line_from_angle(rect, 90, 'left')
    # Length 20, Angle 90 -> x+0, y-20
    assert np.allclose(p2, [20, 65])

def test_symmetric_flipper_angles():
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
    
    assert sim.flipper_resting_angle == -45
    
    # Run update loop for a bit to let angles settle
    for _ in range(100):
        sim._update_flipper_angles(0.1)
        
    # Left should settle at -45
    assert np.isclose(sim.current_left_angle, -45, atol=1.0)
    
    # Right should settle at 180 - (-45) = 225
    assert np.isclose(sim.current_right_angle, 225, atol=1.0)

def test_collision_detection_static():
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
    assert not np.allclose(ball['pos'], [50.0, 50.0])

def test_collision_detection_thickness():
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
    assert np.allclose(ball['pos'], [50.0, 40.0])
    
    # With thickness 15 (effective radius = 5 + 7.5 = 12.5)
    # Distance 10 < 12.5 -> Collision!
    sim._check_line_collision(ball, p1, p2, active=False, thickness=15)
    assert not np.allclose(ball['pos'], [50.0, 40.0])

def test_3d_projection():
    width, height = 600, 800
    sim = SimulatedFrameCapture(width=width, height=height)
    
    # Test Center Projection
    # Center of table (width/2, height/2, 0) should project roughly to center of screen
    sx, sy = sim._project_3d(width/2, height/2, 0)
    
    # Should be close to screen center (width/2, height/2)
    assert abs(sx - width/2) < 20
    assert abs(sy - height/2) < 20
    
    # Test Top vs Bottom
    # Top (y=0) should be HIGHER on screen (smaller sy) than Bottom (y=height)
    _, sy_top = sim._project_3d(width/2, 0, 0)
    _, sy_bottom = sim._project_3d(width/2, height, 0)
    
    assert sy_top < sy_bottom

def test_draw_frame_3d():
    sim = SimulatedFrameCapture(width=100, height=100)
    # Add a ball
    sim.balls.append({
        'pos': np.array([50.0, 50.0]),
        'vel': np.array([0.0, 0.0]),
        'lost': False
    })
    
    # Should run without error
    sim._draw_frame()
    
    assert sim.frame is not None
    assert sim.frame.shape == (100, 100, 3)
