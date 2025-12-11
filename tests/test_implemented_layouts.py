import unittest
import os
import sys
# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from pbwizard.vision import SimulatedFrameCapture

class TestImplementedLayouts(unittest.TestCase):
    def setUp(self):
        os.environ['HEADLESS_SIM'] = 'true'
        self.sim = SimulatedFrameCapture()

    def test_spooky_family_load(self):
        print("\nTesting Spooky Family Layout...")
        success = self.sim.load_layout("spooky_family")
        self.assertTrue(success, "Failed to load spooky_family.json")
        self.assertEqual(self.sim.layout.name, "Spooky Family")
        self.assertEqual(len(self.sim.layout.bumpers), 5)
        self.assertEqual(len(self.sim.layout.drop_targets), 3)

    def test_twilight_zone_load(self):
        print("\nTesting Twilight Zone Layout...")
        success = self.sim.load_layout("twilight_zone")
        self.assertTrue(success, "Failed to load twilight_zone.json")
        self.assertEqual(self.sim.layout.name, "Twilight Zone")
        self.assertEqual(len(self.sim.layout.bumpers), 5)
        # Check specific features
        self.assertEqual(len(self.sim.layout.captures), 1)

    def test_medieval_madness_load(self):
        print("\nTesting Medieval Madness Layout...")
        success = self.sim.load_layout("medieval_madness")
        self.assertTrue(success, "Failed to load medieval_madness.json")
        self.assertEqual(self.sim.layout.name, "Medieval Madness")
        self.assertEqual(len(self.sim.layout.bumpers), 4)
        self.assertEqual(len(self.sim.layout.drop_targets), 3)

if __name__ == '__main__':
    unittest.main()
