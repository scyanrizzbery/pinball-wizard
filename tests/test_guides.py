import pytest
import numpy as np
from pbwizard.physics import PymunkEngine
from pbwizard.vision import PinballLayout

class TestGuides:
    @pytest.fixture
    def engine(self):
        layout = PinballLayout()
        # Use standard dimensions
        return PymunkEngine(layout, 600, 1200)

    def test_default_guides(self, engine):
        """Verify default guides are created."""
        assert len(engine.guide_shapes) == 2
        # Check thickness
        for shape in engine.guide_shapes:
            assert shape.radius == 25.0

    def test_update_guide_thickness(self, engine):
        """Verify updating thickness works."""
        engine.update_guide_params(thickness=40.0)
        assert len(engine.guide_shapes) == 2
        for shape in engine.guide_shapes:
            assert shape.radius == 40.0

    def test_update_guide_length(self, engine):
        """Verify updating length changes geometry."""
        # Get initial start point of left guide
        initial_shape = engine.guide_shapes[0]
        initial_start = initial_shape.a
        
        # Increase length scale
        engine.update_guide_params(length_scale=1.5)
        
        new_shape = engine.guide_shapes[0]
        new_start = new_shape.a
        
        # Longer guide means start point should be higher (smaller Y)
        assert new_start[1] < initial_start[1]

    def test_update_guide_angle(self, engine):
        """Verify updating angle changes geometry."""
        # Get initial start point of left guide
        initial_shape = engine.guide_shapes[0]
        initial_start = initial_shape.a
        
        # Apply angle offset (positive = outward/left for left guide)
        engine.update_guide_params(angle_offset=20.0)
        
        new_shape = engine.guide_shapes[0]
        new_start = new_shape.a
        
        # Angled out means start point should be further left (smaller X)
        assert new_start[0] < initial_start[0]
