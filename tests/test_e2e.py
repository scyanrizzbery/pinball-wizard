import unittest
import numpy as np
import cv2
from unittest.mock import MagicMock
import sys
import os

# Add src to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from pbwizard.vision import BallTracker, ZoneManager
from pbwizard.agent import ReflexAgent
from pbwizard.hardware import MockController

class TestE2E(unittest.TestCase):
    def test_reflex_agent_triggers_flippers(self):
        # Setup
        width, height = 1920, 1080
        zone_manager = ZoneManager(width, height)
        hw = MockController()
        hw.flip_left = MagicMock()
        hw.flip_right = MagicMock()
        agent = ReflexAgent(zone_manager, hw)

        # Test Case 1: Ball in Left Zone
        # Left zone is approx x: 20-40%, y: 70-90%
        ball_x = int(width * 0.3)
        ball_y = int(height * 0.8)
        # Must pass velocity > 0 (moving down) to trigger flip
        agent.act((ball_x, ball_y), width, height, velocity=(0, 10))
        hw.flip_left.assert_called_once()
        hw.flip_right.assert_not_called()

        # Reset mocks
        hw.flip_left.reset_mock()
        hw.flip_right.reset_mock()

        # Test Case 2: Ball in Right Zone
        # Right zone is approx x: 60-80%, y: 70-90%
        ball_x = int(width * 0.7)
        ball_y = int(height * 0.8)
        agent.act((ball_x, ball_y), width, height, velocity=(0, 10))
        hw.flip_left.assert_not_called()
        hw.flip_right.assert_called_once()

        # Reset mocks
        hw.flip_left.reset_mock()
        hw.flip_right.reset_mock()

        # Test Case 3: Ball Out of Zone (High up)
        ball_x = int(width * 0.5)
        ball_y = int(height * 0.2)
        agent.act((ball_x, ball_y), width, height, velocity=(0, 10))
        hw.flip_left.assert_not_called()
        hw.flip_right.assert_not_called()

    def test_ball_tracker_detects_ball(self):
        tracker = BallTracker()
        
        # Create a synthetic frame with a "silver" ball
        frame = np.zeros((100, 100, 3), dtype=np.uint8)
        # Draw a circle that matches the silver HSV range
        # Silver is roughly low saturation, high value. 
        # In BGR, (200, 200, 200) is light gray.
        cv2.circle(frame, (50, 50), 10, (200, 200, 200), -1)
        
        # Note: The BallTracker uses HSV thresholding.
        # (200, 200, 200) BGR -> (0, 0, 200) HSV (approx)
        # Tracker range: Lower(0, 0, 150), Upper(180, 50, 255)
        # So (200, 200, 200) should be detected.
        
        ball_pos, processed_frame = tracker.process_frame(frame)
        
        self.assertIsNotNone(ball_pos)
        # Allow some margin of error for centroid calculation
        self.assertTrue(45 <= ball_pos[0] <= 55)
        self.assertTrue(45 <= ball_pos[1] <= 55)

if __name__ == "__main__":
    unittest.main()
