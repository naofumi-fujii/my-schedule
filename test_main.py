import unittest
from unittest.mock import patch, MagicMock
import datetime
import pytz
import json
from io import StringIO
import sys

import main
from main import find_available_slots

class TestMySchedule(unittest.TestCase):
    def setUp(self):
        self.jst = pytz.timezone('Asia/Tokyo')
        
    @patch('sys.stdout', new_callable=StringIO)
    @patch('main.get_credentials')
    @patch('main.discovery.build')
    def test_main_no_events(self, mock_build, mock_get_credentials, mock_stdout):
        # Import main here to avoid issues with the test runner
        import main as main_module
        
        # Mock is_holiday function to always return False
        original_is_holiday = main_module.is_holiday
        main_module.is_holiday = lambda service, date: False
        # Mock the calendar service
        mock_service = MagicMock()
        mock_events_list = MagicMock()
        mock_events_list.return_value.execute.return_value = {'items': []}
        mock_service.events().list = mock_events_list
        mock_build.return_value = mock_service
        
        try:
            # Run with test args
            with patch('sys.argv', ['main.py']):
                from main import main
                main()
                
            self.assertIn('No upcoming events found', mock_stdout.getvalue())
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
            mock_service.events().list().execute.return_value = {'items': []}
            
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
            for start, end in available_slots:
                # Slots should be during business hours (after 10:00 and before 18:00)
                self.assertGreaterEqual(start.hour, 10)
                self.assertLessEqual(end.hour, 18)
                
                # If end hour is 18, minutes should be 0
                if end.hour == 18:
                    self.assertEqual(end.minute, 0)
                    
                # Duration should be at least 1 hour
                duration = (end - start).total_seconds() / 3600
                self.assertGreaterEqual(duration, 1.0)
            
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
            tomorrow_noon_jst = tomorrow_noon.replace(tzinfo=pytz.UTC).astimezone(self.jst)
            tomorrow_noon_jst_str = tomorrow_noon_jst.isoformat()
            
            tomorrow_one = tomorrow.replace(hour=13, minute=0, second=0)
            tomorrow_one_jst = tomorrow_one.replace(tzinfo=pytz.UTC).astimezone(self.jst)
            tomorrow_one_jst_str = tomorrow_one_jst.isoformat()
            
            # Mock calendar with one meeting
            mock_service.events().list().execute.return_value = {
                'items': [
                    {
                        'start': {'dateTime': tomorrow_noon_jst_str},
                        'end': {'dateTime': tomorrow_one_jst_str}
                    }
                ]
            }
            
            # Find available slots
            day_after = tomorrow + datetime.timedelta(days=1)
            available_slots = find_available_slots(mock_service, tomorrow, day_after)
            
            # Should find slots before and after the meeting
            self.assertTrue(len(available_slots) >= 2)
            
            # Verify slots don't overlap with the meeting (allowing for 30 min buffer)
            for start, end in available_slots:
                # Convert to same timezone for comparison
                start_utc = start.astimezone(pytz.UTC)
                end_utc = end.astimezone(pytz.UTC)
                
                # Slot should either end before meeting starts (with 30 min buffer) or
                # start after meeting ends (with 30 min buffer)
                meeting_start_with_buffer = tomorrow_noon - datetime.timedelta(minutes=30)
                meeting_end_with_buffer = tomorrow_one + datetime.timedelta(minutes=30)
                
                self.assertTrue(
                    end_utc <= meeting_start_with_buffer.replace(tzinfo=pytz.UTC) or 
                    start_utc >= meeting_end_with_buffer.replace(tzinfo=pytz.UTC)
                )
            
        finally:
            # Restore original is_holiday function
            main_module.is_holiday = original_is_holiday

if __name__ == '__main__':
    unittest.main()