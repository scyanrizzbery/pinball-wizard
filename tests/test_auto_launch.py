import pytest
import time
from pbwizard.physics import PymunkEngine
from pbwizard.vision import PinballLayout

def test_auto_launch_logic():
    """Test that the plunger fires automatically when a ball is in the launch lane."""
    # Use real layout with defaults
    layout = PinballLayout()
    layout.config = {'auto_plunge_enabled': True}
    layout.physics_params = {'auto_plunge_enabled': True}

    engine = PymunkEngine(layout, layout.width, layout.height)
    # Ensure config has auto_plunge enabled
    engine.auto_plunge_enabled = True
    
    # 1. Add ball to plunger lane

    
    
    # 1. Add ball to plunger lane
    # Plunger is at bottom right. Width=0.6, Height=1.2
    # Plunger rest Y is 0.95 * height = 1.14
    # Plunger X is approx 0.95 * width = 0.57
    engine.add_ball(pos=(layout.width * 0.95, layout.height * 0.9))
    
    # Ball is added via callback, so we need to step the simulation once to let it appear
    engine.update(0.016)

    # Verify ball exists
    assert len(engine.balls) == 1
    ball = engine.balls[0]
    initial_y = ball.position.y
    
    # 2. Run simulation for a few seconds
    # The auto-plunge logic should detect the ball and fire
    launched = False
    for i in range(200): # 200 * 0.016 = ~3.2 seconds
        engine.update(0.016)
        
        # Check if ball moved significantly upwards (launched)
        # origin is top-left? NO, pymunk is usually bottom-left? 
        # Wait, previous analysis said physics is Top-Left (y grows down).
        # Plunger is at bottom (high Y). Launch means Y decreases.
        if ball.position.y < initial_y - 0.2: 
            launched = True
            break
            
    assert launched, "Ball should have been auto-launched from the plunger lane"
