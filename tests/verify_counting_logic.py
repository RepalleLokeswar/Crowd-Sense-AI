
import sys
import os

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from counting import Zone
import unittest

class TestCountingLogic(unittest.TestCase):
    def setUp(self):
        # Create a zone: x1=0, y1=0, x2=100, y2=100
        self.zone = Zone("TestZone", (0, 0, 100, 100), (0, 255, 0))

    def test_entry_logic(self):
        # Person ID 1 enters the zone
        centroid_in = (50, 50)
        self.zone.count_entry(1, centroid_in)
        
        self.assertIn(1, self.zone.active_ids)
        self.assertIn(1, self.zone.counted_ids)
        self.assertEqual(self.zone.count, 1)
        self.assertEqual(self.zone.total_count, 1) # First time entry

    def test_exit_logic(self):
        # Person ID 1 enters
        self.zone.count_entry(1, (50, 50))
        # Person ID 1 exits
        self.zone.count_entry(1, (150, 150))
        
        self.assertNotIn(1, self.zone.active_ids)
        self.assertEqual(self.zone.count, 0)
        # Total count should remain 1 (cumulative)
        self.assertEqual(self.zone.total_count, 1)

    def test_reentry_hysteresis(self):
        # ID 1 enters
        self.zone.count_entry(1, (50, 50))
        # ID 1 exits
        self.zone.count_entry(1, (150, 150))
        
        # ID 1 quickly re-enters (e.g. jitter)
        self.zone.count_entry(1, (50, 50))
        
        # Should be active again
        self.assertIn(1, self.zone.active_ids)
        # Should NOT increment total count again (same session)
        self.assertEqual(self.zone.total_count, 1)

    def test_long_absence_reset(self):
        # ID 1 enters
        self.zone.count_entry(1, (50, 50))
        # ID 1 exits
        self.zone.count_entry(1, (150, 150))
        
        # Simulate passing frames
        for _ in range(self.zone.HYSTERESIS_THRESHOLD + 5):
            self.zone.count_entry(1, (150, 150)) # Still outside
            
        # ID 1 re-enters after long time
        self.zone.count_entry(1, (50, 50))
        
        # Should be active
        self.assertIn(1, self.zone.active_ids)
        # Should increment total count again (new session)
        self.assertEqual(self.zone.total_count, 2)

    def test_unconfirmed_id(self):
        # ID -1 (unconfirmed) should be ignored
        self.zone.count_entry(-1, (50, 50))
        self.assertEqual(self.zone.count, 0)

if __name__ == '__main__':
    unittest.main()
