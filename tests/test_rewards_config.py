import unittest
import json
import os
from unittest.mock import MagicMock, patch
from pbwizard.environment import PinballEnv

class TestRewardsConfig(unittest.TestCase):
    def setUp(self):
        self.config_path = "config.json"
        # Backup existing config
        if os.path.exists(self.config_path):
            with open(self.config_path, 'r') as f:
                self.original_config = f.read()
        else:
            self.original_config = None

    def tearDown(self):
        # Restore config
        if self.original_config:
            with open(self.config_path, 'w') as f:
                f.write(self.original_config)
        elif os.path.exists(self.config_path):
            os.remove(self.config_path)

    def test_load_rewards_config(self):
        # Create a mock config with custom rewards
        custom_rewards = {
            "score_log_scale": 0.5,
            "combo_increase_factor": 0.2,
            "multiplier_increase_factor": 1.0,
            "flipper_penalty": 0.01,
            "bumper_hit": 2.0,
            "drop_target_hit": 5.0,
            "rail_hit": 1.5
        }
        config_data = {"rewards": custom_rewards}

        with open(self.config_path, 'w') as f:
            json.dump(config_data, f)

        # Mock dependencies
        vision_mock = MagicMock()
        hw_mock = MagicMock()
        score_mock = MagicMock()

        env = PinballEnv(vision_mock, hw_mock, score_mock, headless=True)

        # Check if rewards are loaded correctly
        self.assertEqual(env.rewards_config['score_log_scale'], 0.5)
        self.assertEqual(env.rewards_config['bumper_hit'], 2.0)

    def test_default_rewards(self):
        # Ensure config file doesn't exist or has no rewards
        if os.path.exists(self.config_path):
            os.remove(self.config_path)

        # Mock dependencies
        vision_mock = MagicMock()
        hw_mock = MagicMock()
        score_mock = MagicMock()

        env = PinballEnv(vision_mock, hw_mock, score_mock, headless=True)

        # Check default values
        self.assertEqual(env.rewards_config['score_log_scale'], 0.1)
        self.assertEqual(env.rewards_config['bumper_hit'], 0.5)

if __name__ == '__main__':
    unittest.main()

