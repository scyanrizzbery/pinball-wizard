import pytest
import os
import sys
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from pbwizard.physics import PymunkEngine
from pbwizard.vision import SimulatedFrameCapture

# Simple mock layout as object with flattened attributes required by PymunkEngine
MOCK_LAYOUT = SimpleNamespace(
    sections=[],
    flippers={'left': {}, 'right': {}},
    bumpers=[],
    drop_targets=[],
    plungers={},
    walls=[],
    rails=[],
    rail_angle_offset=0.0,
    rail_x_offset=0.0,
    rail_y_offset=0.0,
    
    # Flattened flipper attributes used by physics engine
    left_flipper_x_min = 0.2,
    left_flipper_x_max = 0.4,
    left_flipper_y_min = 0.8,
    left_flipper_y_max = 0.85,
    
    right_flipper_x_min = 0.6,
    right_flipper_x_max = 0.8,
    right_flipper_y_min = 0.8,
    right_flipper_y_max = 0.85,
    
    flipper_length = 0.2,
    flipper_width = 0.05
)

def test_engine_initialization_smoke():
    """Smoke test: Verify the physics engine initializes without crashing."""
    try:
        # PymunkEngine(layout, width, height)
        engine = PymunkEngine(MOCK_LAYOUT, 450, 800)
        assert engine is not None
        assert engine.space is not None
        assert engine.width == 450
        assert engine.height == 800
    except Exception as e:
        pytest.fail(f"Engine initialization failed: {e}")

def test_simulation_step_smoke():
    """Smoke test: Verify the simulation can run a single step."""
    try:
        engine = PymunkEngine(MOCK_LAYOUT, 450, 800)
        
        # Run one physics step
        engine.update(1/60.0)
        assert True
    except Exception as e:
        pytest.fail(f"Simulation step failed: {e}")
