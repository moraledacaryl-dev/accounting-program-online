"""Unit tests for historical Beds24 status classification."""
import unittest
from scripts.audit_beds24_statuses import classify_booking


class BookingClassificationTests(unittest.TestCase):
    def test_matching_confirmed(self):
        self.assertEqual(classify_booking([{"status": "confirmed"}], [{"status": "confirmed"}]), ("MATCHED", "confirmed"))

    def test_cancelled_remote_active_local(self):
        self.assertEqual(classify_booking([{"status": "confirmed"}], [{"status": "cancelled"}]), ("CANCELLATION_MISMATCH", "cancelled"))

    def test_cancelled_spelling_equivalence(self):
        self.assertEqual(classify_booking([{"status": "canceled"}], [{"status": "cancelled"}]), ("MATCHED", "cancelled"))

    def test_other_status_difference(self):
        self.assertEqual(classify_booking([{"status": "confirmed"}], [{"status": "new"}]), ("OTHER_STATUS_MISMATCH", "new"))

    def test_missing_remote(self):
        self.assertEqual(classify_booking([{"status": "confirmed"}], []), ("MISSING_IN_BEDS24", ""))

    def test_duplicate_local(self):
        self.assertEqual(classify_booking([{"status": "confirmed"}, {"status": "confirmed"}], [{"status": "confirmed"}]), ("DUPLICATE_LINK", ""))

    def test_duplicate_remote(self):
        self.assertEqual(classify_booking([{"status": "confirmed"}], [{"status": "confirmed"}, {"status": "confirmed"}]), ("DUPLICATE_REMOTE", ""))

    def test_empty_remote_status_not_marked_mismatch(self):
        self.assertEqual(classify_booking([{"status": "confirmed"}], [{"status": ""}]), ("API_ERROR", ""))


if __name__ == "__main__":
    unittest.main()
