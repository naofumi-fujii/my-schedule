import unittest
from unittest.mock import patch, MagicMock
import datetime
import pytz
from io import StringIO

from main import find_available_slots


class TestMySchedule(unittest.TestCase):
    def setUp(self):
        self.jst = pytz.timezone("Asia/Tokyo")

    @patch("sys.stdout", new_callable=StringIO)
    @patch("main.get_credentials")
    @patch("main.discovery.build")
    def test_main_available_slots_empty_calendar(self, mock_build, mock_get_credentials, mock_stdout):
        # Import main here to avoid issues with the test runner
        import main as main_module

        # Mock is_holiday function to always return False
        original_is_holiday = main_module.is_holiday
        main_module.is_holiday = lambda service, date: False
        # Mock the calendar service
        mock_service = MagicMock()
        mock_events_list = MagicMock()
        mock_events_list.return_value.execute.return_value = {"items": []}
        mock_service.events().list = mock_events_list
        mock_build.return_value = mock_service

        try:
            # Run with --available-slots to check available time slots
            with patch("sys.argv", ["main.py", "--available-slots"]):
                from main import main
                main()

            # Check that available slots were found and formatted correctly
            output = mock_stdout.getvalue()
            self.assertIn("Finding available time slots (weekdays, 10:00-18:00)", output)
            self.assertIn("Found", output)
            self.assertIn("10:30 - 17:30", output)  # Should find full day slots
        finally:
            # Restore original is_holiday function
            main_module.is_holiday = original_is_holiday

    def test_find_available_slots_empty_calendar(self):
        # Mock is_holiday function to always return False
        import main as main_module

        original_is_holiday = main_module.is_holiday
        main_module.is_holiday = lambda service, date: False

        try:
            mock_service = MagicMock()
            mock_service.events().list().execute.return_value = {"items": []}

            # Test dates (tomorrow to test day after)
            now = datetime.datetime.utcnow()
            tomorrow = now + datetime.timedelta(days=1)
            day_after = tomorrow + datetime.timedelta(days=1)

            # Run the function (we need to ensure these days are weekdays for this test)
            weekday_adjust = 0
            if tomorrow.weekday() >= 5:  # 5 is Saturday, 6 is Sunday
                weekday_adjust = 8 - tomorrow.weekday()  # Move to next Monday

            tomorrow = tomorrow + datetime.timedelta(days=weekday_adjust)
            day_after = tomorrow + datetime.timedelta(days=1)

            available_slots = find_available_slots(mock_service, tomorrow, day_after)

            # Should find slots on weekdays
            self.assertTrue(len(available_slots) > 0)

            # Check if slot is during business hours
            for slot in available_slots:
                start = slot['start']
                end = slot['end']
                # Business hours are 10:00-18:00 with 30 min buffer
                self.assertTrue(start.hour >= 10)
                self.assertTrue(end.hour <= 18)
                # Duration should be at least 1 hour
                duration = (end - start).total_seconds() / 3600
                self.assertTrue(duration >= 1.0)

        finally:
            # Restore original is_holiday function
            main_module.is_holiday = original_is_holiday

    def test_find_available_slots_with_meetings(self):
        # Mock is_holiday function to always return False
        import main as main_module

        original_is_holiday = main_module.is_holiday
        main_module.is_holiday = lambda service, date: False

        try:
            mock_service = MagicMock()

            # Test dates (make sure they're weekdays)
            now = datetime.datetime.utcnow()
            tomorrow = now + datetime.timedelta(days=1)

            # Adjust to weekday if needed
            if tomorrow.weekday() >= 5:  # 5=Saturday, 6=Sunday
                tomorrow = tomorrow + datetime.timedelta(days=(8 - tomorrow.weekday()))

            # Create a day with one meeting from 12:00-13:00
            tomorrow_noon = tomorrow.replace(hour=12, minute=0, second=0)
            tomorrow_noon_jst = tomorrow_noon.replace(tzinfo=pytz.UTC).astimezone(
                self.jst
            )
            tomorrow_noon_jst_str = tomorrow_noon_jst.isoformat()

            tomorrow_one = tomorrow.replace(hour=13, minute=0, second=0)
            tomorrow_one_jst = tomorrow_one.replace(tzinfo=pytz.UTC).astimezone(
                self.jst
            )
            tomorrow_one_jst_str = tomorrow_one_jst.isoformat()

            # Mock calendar with one meeting
            mock_service.events().list().execute.return_value = {
                "items": [
                    {
                        "start": {"dateTime": tomorrow_noon_jst_str},
                        "end": {"dateTime": tomorrow_one_jst_str},
                    }
                ]
            }

            # Find available slots
            day_after = tomorrow + datetime.timedelta(days=1)
            available_slots = find_available_slots(mock_service, tomorrow, day_after)

            # Should find slots before and after the meeting
            self.assertTrue(len(available_slots) >= 2)

            # Verify slots don't overlap with the meeting (allowing for 30 min buffer)
            for slot in available_slots:
                start = slot['start']
                end = slot['end']
                # Check if slot is before meeting (with buffer)
                if end <= tomorrow_noon_jst - datetime.timedelta(minutes=30):
                    continue
                # Check if slot is after meeting (with buffer)
                if start >= tomorrow_one_jst + datetime.timedelta(minutes=30):
                    continue
                # If we get here, slot overlaps with meeting time
                self.fail("Found slot overlapping with meeting time")

        finally:
            # Restore original is_holiday function
            main_module.is_holiday = original_is_holiday


if __name__ == "__main__":
    unittest.main()
