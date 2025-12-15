
import unittest
import os
import sys
import json
import logging
import time

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from pbwizard.vision import SimulatedFrameCapture

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class TestAutoStartRegression(unittest.TestCase):
    def setUp(self):
        os.environ['HEADLESS_SIM'] = 'True'
        
        # Ensure config.json has auto_plunge_enabled: true
        if os.path.exists("config.json"):
            with open('config.json', 'r') as f:
                self.original_config = json.load(f)
        else:
            self.original_config = {}
            
        config = self.original_config.copy()
        # config['auto_plunge_enabled'] = True  <-- Default should now be True!
        # Let's ensure it's NOT in config to test the code default
        if 'auto_plunge_enabled' in config:
            del config['auto_plunge_enabled']
            
        with open('config.json', 'w') as f:
            json.dump(config, f, indent=4)
            
        self.capture = SimulatedFrameCapture()

    def tearDown(self):
        # Restore config
         with open('config.json', 'w') as f:
            json.dump(self.original_config, f, indent=4)

    def test_startup_and_config_exposure(self):
        """Test startup preference AND get_config exposure."""
        logger.info(f"Startup check: auto_plunge_enabled = {self.capture.auto_plunge_enabled}")
        self.assertTrue(self.capture.auto_plunge_enabled, 
                       "Should be Enabled on startup based on config.json")
        
        # Verify get_config exposure (CRITICAL for frontend sync)
        config = self.capture.get_config()
        self.assertIn('auto_plunge_enabled', config, "get_config MUST include auto_plunge_enabled")
        self.assertTrue(config['auto_plunge_enabled'], "get_config should return True")

    def test_persistence_after_layout_switch(self):
        """Test that auto-start remains enabled after switching layouts."""
        self.capture.load_layout('default')
        # Check object state
        self.assertTrue(self.capture.auto_plunge_enabled, 
                       "Should remain Enabled after loading 'default'")
        
        # Check config exposure again (regression check)
        config = self.capture.get_config()
        self.assertTrue(config['auto_plunge_enabled'], 
                       "get_config should return True after layout load")

    def test_switch_layout_and_back(self):
        """Test that auto-start persists when switching to a layout and back, AND when changed."""
        # Initial check
        self.assertTrue(self.capture.auto_plunge_enabled, "Should be Enabled initially")
        
        # Switch to 'cathedral'
        logger.info("Switching to 'cathedral' layout")
        self.capture.load_layout('cathedral')
        self.assertTrue(self.capture.auto_plunge_enabled, 
                       "Should remain Enabled after switching to 'cathedral'")
                       
        # Switch back to 'default'
        logger.info("Switching back to 'default' layout")
        self.capture.load_layout('default')
        self.assertTrue(self.capture.auto_plunge_enabled, 
                       "Should remain Enabled after switching back to 'default'")

        # TEST RUNTIME CHANGE
        logger.info("Disabling Auto-Start at runtime...")
        self.capture.update_physics_params({'auto_plunge_enabled': False})
        
        # Verify it updated immediately
        config = self.capture.get_config()
        self.assertFalse(config['auto_plunge_enabled'], 
                        "get_config should return False after runtime update")
        self.assertFalse(self.capture.auto_plunge_enabled, 
                        "Internal attribute should be False")

        # Switch layout again
        logger.info("Switching to 'cathedral' with Disabled Auto-Start")
        self.capture.load_layout('cathedral')
        self.assertFalse(self.capture.auto_plunge_enabled, 
                        "Should remain Disabled after switching layout")
        
        # Switch back
        logger.info("Switching back to 'default'")
        self.capture.load_layout('default')
        self.assertFalse(self.capture.auto_plunge_enabled, 
                        "Should remain Disabled after switching back")

if __name__ == '__main__':
    unittest.main()
