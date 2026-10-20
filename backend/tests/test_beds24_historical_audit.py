"""Unit tests for historical Beds24 status classification."""
import unittest
from scripts.audit_beds24_statuses import classify_booking, effective_classification


class BookingClassificationTests(unittest.TestCase):
    def test_matching_confirmed(self):
        self.assertEqual(classify_booking([{"status": "confirmed"}], [{"status": "confirmed"}]), ("MATCHED", "confirmed"))

    def test_cancelled_remote_active_local(self):
        self.assertEqual(classify_booking([{"status": "confirmed"}], [{"status": "cancelled"}]), ("CANCELLATION_MISMATCH", "cancelled"))

    def test_cancelled_spelling_equivalence(self):
        self.assertEqual(classify_booking([{"status": "canceled"}], [{"status": "cancelled"}]), ("MATCHED", "cancelled"))

    def test_normalizes_beds24_new_to_confirmed(self):
        self.assertEqual(classify_booking([{"status": "confirmed"}], [{"status": "new"}]), ("MATCHED", "new"))

    def test_normalizes_beds24_reserved_to_confirmed(self):
        self.assertEqual(classify_booking([{"status": "confirmed"}], [{"status": "reserved"}]), ("MATCHED", "reserved"))

    def test_normalizes_beds24_arrived_to_checked_in(self):
        self.assertEqual(classify_booking([{"status": "checked_in"}], [{"status": "arrived"}]), ("MATCHED", "arrived"))

    def test_genuine_status_difference(self):
        self.assertEqual(classify_booking([{"status": "checked_out"}], [{"status": "new"}]), ("OTHER_STATUS_MISMATCH", "new"))

    def test_substatus_uses_same_precedence_as_sync(self):
        self.assertEqual(classify_booking([{"status": "confirmed"}], [{"status": "new", "subStatus": "cancelled"}]), ("CANCELLATION_MISMATCH", "new"))

    def test_reclassifies_old_csv_mismatch_without_new_api_call(self):
        row = {"classification": "OTHER_STATUS_MISMATCH", "accounting_status": "confirmed", "beds24_status": "new"}
        self.assertEqual(effective_classification(row), "STATUS_ALIAS_MATCH")

    def test_retains_missing_remote_status_exception(self):
        row = {"classification": "MISSING_IN_BEDS24", "accounting_status": "confirmed", "beds24_status": ""}
        self.assertEqual(effective_classification(row), "MISSING_IN_BEDS24")

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
