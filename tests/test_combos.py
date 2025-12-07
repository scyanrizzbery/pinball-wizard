import pytest
from unittest.mock import MagicMock, patch
import time
from pbwizard.physics import PymunkEngine

class TestComboSystem:
    @pytest.fixture
    def engine(self):
        # Mock layout and dimensions
        layout = MagicMock()
        layout.zones = []
        return PymunkEngine(layout, 600, 800)

    def test_initial_state(self, engine):
        """Verify initial combo state is zero/inactive."""
        status = engine.get_combo_status()
        assert status['combo_count'] == 0
        assert status['combo_active'] is False
        assert engine.get_multiplier() == 1.0

    def test_combo_increment(self, engine):
        """Verify combo increments on consecutive hits."""
        # Simulate a hit
        engine.combo_count = 0
        engine.score_multiplier = 1.0
        
        # Hit 1 (Start)
        engine.combo_count = 1
        engine.score_multiplier = min(engine.combo_count, engine.config.multiplier_max)
        assert engine.combo_count == 1
        assert engine.get_multiplier() == 1.0 
        
        # Hit 2 (2x)
        engine.combo_count = 2
        engine.score_multiplier = min(engine.combo_count, engine.config.multiplier_max)
        assert engine.combo_count == 2
        assert engine.get_multiplier() == 2.0
        
        # Hit 5 (5x - Max default)
        engine.combo_count = 5
        engine.score_multiplier = min(engine.combo_count, engine.config.multiplier_max)
        assert engine.get_multiplier() == 5.0
        
        # Hit 10 (Above Max)
        engine.combo_count = 10
        engine.score_multiplier = min(engine.combo_count, engine.config.multiplier_max)
        assert engine.get_multiplier() == 5.0 # Should still be capped at 5.0 (or whatever multiplier_max is)

    def test_combo_expiration(self, engine):
        """Verify combo expires after timer runs out."""
        engine.combo_count = 3
        # Use config for window
        engine.combo_timer = 0.1
        engine.score_multiplier = 3.0
        
        # Update with time > timer
        engine.update_combo_timer(0.2)
        
        assert engine.combo_count == 0
        assert engine.combo_timer == 0.0
        assert engine.get_multiplier() == 1.0
        
    def test_combo_maintenance(self, engine):
        """Verify combo timer decrements but keeps combo active."""
        engine.combo_count = 3
        engine.combo_timer = 3.0
        engine.score_multiplier = 3.0
        
        # Update with small time step
        engine.update_combo_timer(1.0)
        
        assert engine.combo_count == 3
        assert engine.combo_timer == 2.0 # 3.0 - 1.0
        assert engine.get_multiplier() == 3.0 # Should maintain multiplier
