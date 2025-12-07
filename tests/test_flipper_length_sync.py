
import pytest
from unittest.mock import MagicMock, patch
from pbwizard.vision import SimulatedFrameCapture
from pbwizard.config import PhysicsConfig

class MockLayout:
    def __init__(self):
        self.physics_params = {}
        self.left_flipper_x_min = 0.2
        self.left_flipper_x_max = 0.25 # Old default
        self.right_flipper_x_min = 0.8
        self.right_flipper_x_max = 0.85 
        self.left_flipper_y_min = 0.8
        self.left_flipper_y_max = 0.9
        self.right_flipper_y_min = 0.8
        self.right_flipper_y_max = 0.9

def test_flipper_length_sync():
    # Setup
    # Initialize with minimal arguments
    capture = SimulatedFrameCapture(width=1000, height=1000)
    
    # Inject Mock Layout
    capture.layout = MockLayout()
    
    # Inject Mock Physics Engine
    capture.physics_engine = MagicMock()
    # Mock the config object
    capture.physics_engine.config = PhysicsConfig()
    capture.physics_engine.config.flipper_length = 0.12 # Default
    
    # Mock apply_config_changes
    capture.physics_engine.apply_config_changes = MagicMock()

    # Test 1: Update via flipper_length param directly
    new_length = 0.2
    params = {'flipper_length': new_length}
    capture.update_physics_params(params)
    
    # Check if config was updated via update() call in SimulatedFrameCapture?
    # No, capture.update_physics_params calls engine.config.update() then engine.apply_config_changes()
    # But wait, config.update() is a method on the real PhysicsConfig object.
    # We used a real PhysicsConfig object on the mock engine, so it should work.
    
    # Check if layout updated
    # Left flipper: x_max = x_min + length
    print(f"Left Flipper: Min={capture.layout.left_flipper_x_min}, Max={capture.layout.left_flipper_x_max}, Expected diff={new_length}")
    assert capture.layout.left_flipper_x_max == capture.layout.left_flipper_x_min + new_length
    
    # Right flipper: x_max = x_min + length (based on logic I wrote)
    print(f"Right Flipper: Min={capture.layout.right_flipper_x_min}, Max={capture.layout.right_flipper_x_max}, Expected diff={new_length}")
    assert capture.layout.right_flipper_x_max == capture.layout.right_flipper_x_min + new_length
    
    # Test 2: Update position with EXISTING length
    # Mock engine length
    capture.physics_engine.config.flipper_length = 0.15
    
    params = {'left_flipper_pos_x': 0.3}
    capture.update_physics_params(params)
    
    assert capture.layout.left_flipper_x_min == 0.3
    # Should use 0.15 from engine config (since flipper_length param is NOT in this call)
    assert capture.layout.left_flipper_x_max == 0.3 + 0.15

if __name__ == "__main__":
    test_flipper_length_sync()
    print("Tests passed!")
