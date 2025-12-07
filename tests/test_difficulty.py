import pytest
from unittest.mock import MagicMock
from pbwizard.agent import ReflexAgent

class TestAIDifficulty:
    @pytest.fixture
    def zone_manager(self):
        return MagicMock()
        
    @pytest.fixture
    def hardware(self):
        return MagicMock()

    def test_difficulty_presets(self, zone_manager, hardware):
        """Verify difficulty presets load correct parameters."""
        
        # Easy Mode
        agent_easy = ReflexAgent(hardware, difficulty='easy')
        assert agent_easy.difficulty == 'easy'
        assert agent_easy.COOLDOWN == 45
        assert agent_easy.VY_THRESHOLD == 100
        assert agent_easy.USE_VELOCITY_PREDICTION is False
        
        # Medium Mode
        agent_medium = ReflexAgent(hardware, difficulty='medium')
        assert agent_medium.difficulty == 'medium'
        assert agent_medium.COOLDOWN == 30
        assert agent_medium.VY_THRESHOLD == 50
        assert agent_medium.USE_VELOCITY_PREDICTION is False
        
        # Hard Mode
        agent_hard = ReflexAgent(hardware, difficulty='hard')
        assert agent_hard.difficulty == 'hard'
        assert agent_hard.COOLDOWN == 20
        assert agent_hard.VY_THRESHOLD == 20
        assert agent_hard.USE_VELOCITY_PREDICTION is True

    def test_default_difficulty(self, zone_manager, hardware):
        """Verify default difficulty is medium."""
        agent = ReflexAgent(hardware)
        assert agent.difficulty == 'medium'
        assert agent.COOLDOWN == 30

    def test_invalid_difficulty(self, zone_manager, hardware):
        """Verify invalid difficulty falls back to medium."""
        agent = ReflexAgent(hardware, difficulty='invalid_mode')
        # Should load medium params
        assert agent.COOLDOWN == 30
        assert agent.VY_THRESHOLD == 50
