import unittest
from unittest.mock import patch, MagicMock
import datetime
import pytz
import json
from io import StringIO

from main import (
    find_available_slots, 
    to_jst, 
    to_utc_str, 
    get_day_start_end,
    get_business_hours,
    format_output_json,
    format_output_text
)


class TestMySchedule(unittest.TestCase):
    def setUp(self):
        self.jst = pytz.timezone("Asia/Tokyo")
        
    def test_timezone_utilities(self):
        """タイムゾーン関連ユーティリティ関数のテスト"""
        # to_jst関数のテスト
        utc_dt = datetime.datetime(2025, 4, 1, 10, 0, 0, tzinfo=pytz.UTC)
        jst_dt = to_jst(utc_dt)
        self.assertEqual(jst_dt.hour, 19)  # UTC+9時間
        self.assertEqual(jst_dt.tzinfo.zone, "Asia/Tokyo")
        
        # タイムゾーン情報なしのdatetimeを渡した場合
        naive_dt = datetime.datetime(2025, 4, 1, 10, 0, 0)
        jst_dt2 = to_jst(naive_dt)
        self.assertEqual(jst_dt2.hour, 19)  # UTCとして扱われてUTC+9時間
        self.assertEqual(jst_dt2.tzinfo.zone, "Asia/Tokyo")
        
        # to_utc_str関数のテスト
        jst_dt = self.jst.localize(datetime.datetime(2025, 4, 1, 19, 0, 0))
        utc_str = to_utc_str(jst_dt)
        self.assertTrue("2025-04-01T10:00:00" in utc_str)
        
        # get_day_start_end関数のテスト
        dt = self.jst.localize(datetime.datetime(2025, 4, 1, 12, 30, 0))
        start, end = get_day_start_end(dt)
        self.assertEqual(start.hour, 0)
        self.assertEqual(start.minute, 0)
        self.assertEqual(end.day, 2)  # 次の日
        
        # get_business_hours関数のテスト
        dt = self.jst.localize(datetime.datetime(2025, 4, 1, 12, 30, 0))
        start, end, eff_start, eff_end = get_business_hours(dt)
        self.assertEqual(start.hour, 10)  # 営業開始10:00
        self.assertEqual(end.hour, 18)    # 営業終了18:00
        self.assertEqual(eff_start.hour, 10)  # 実効開始10:30
        self.assertEqual(eff_start.minute, 30)
        self.assertEqual(eff_end.hour, 17)    # 実効終了17:30
        self.assertEqual(eff_end.minute, 30)
        
    def test_format_output(self):
        """出力フォーマット関数のテスト"""
        # テスト用の空き時間データ
        jst = pytz.timezone("Asia/Tokyo")
        slots = [
            {
                'start': jst.localize(datetime.datetime(2025, 4, 1, 10, 30, 0)),
                'end': jst.localize(datetime.datetime(2025, 4, 1, 12, 30, 0)),
                'duration': 2.0
            },
            {
                'start': jst.localize(datetime.datetime(2025, 4, 1, 14, 30, 0)),
                'end': jst.localize(datetime.datetime(2025, 4, 1, 17, 30, 0)),
                'duration': 3.0
            }
        ]
        
        # JSON形式出力のテスト
        json_output = format_output_json(slots)
        data = json.loads(json_output)
        self.assertEqual(len(data['slots']), 2)
        self.assertEqual(data['total_hours'], 5.0)
        
        # テキスト形式出力のテスト
        text_output = format_output_text(slots, 1.0, False, True, 'ja')
        self.assertIn("Finding available time slots", text_output)
        self.assertIn("Found 2 available time slots", text_output)
        self.assertIn("合計空き時間: 5.00時間", text_output)
        
        # 合計時間表示なしのテスト
        text_output_no_total = format_output_text(slots, 1.0, False, False, 'ja')
        self.assertNotIn("合計空き時間", text_output_no_total)

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

            # Create a time in JST timezone directly (for 12:00-13:00 JST business hours)
            jst = pytz.timezone("Asia/Tokyo")
            tomorrow_jst = tomorrow.replace(tzinfo=pytz.UTC).astimezone(jst)
            
            # Set the meeting to occur during business hours (12:00-13:00 JST)
            tomorrow_noon_jst = tomorrow_jst.replace(hour=12, minute=0, second=0, microsecond=0)
            tomorrow_noon_jst_str = tomorrow_noon_jst.isoformat()
            
            tomorrow_one_jst = tomorrow_jst.replace(hour=13, minute=0, second=0, microsecond=0)
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

            # Find available slots (use min_hours=1.0 explicitly)
            day_after = tomorrow + datetime.timedelta(days=1)
            available_slots = find_available_slots(mock_service, tomorrow, day_after, min_hours=1.0)
            
            # Should find slots before and after the meeting
            self.assertTrue(len(available_slots) >= 2, 
                           f"Expected at least 2 slots but found {len(available_slots)}")

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
