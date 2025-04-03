# -*- coding: utf-8 -*-
from __future__ import print_function
import httplib2
import os
import sys

from apiclient import discovery
from oauth2client import client
from oauth2client import tools
from oauth2client.file import Storage

import datetime
from dateutil import parser as date_parser
import pytz
import json

try:
    import argparse

    parser = argparse.ArgumentParser(parents=[tools.argparser])
    parser.add_argument(
        "--format",
        "-f",
        default="text",
        choices=["text", "json"],
        help="Output format: text or json",
    )
    parser.add_argument(
        "--available-slots",
        "-a",
        nargs="?",
        const=1,
        type=float,
        help="Show available time slots during business hours (10:00-18:00) with optional minimum hours (e.g. -a 2 for 2+ hours)",
    )
    parser.add_argument(
        "--show-total-hours",
        "-t",
        action="store_true",
        help="Show total available hours when using --available-slots",
    )
    parser.add_argument(
        "--weekday-lang",
        "-w",
        default="ja",
        choices=["ja", "en"],
        help="Weekday language: ja (Japanese) or en (English)",
    )
    parser.add_argument(
        "--include-holidays",
        action="store_true",
        help="Include holidays in results (holidays are excluded by default)",
    )
    # Only parse args when run as script, not when imported
    flags = None
except ImportError:
    flags = None

# If modifying these scopes, delete your previously saved credentials
# at ~/.credentials/calendar-python-quickstart.json
SCOPES = "https://www.googleapis.com/auth/calendar.readonly"
CLIENT_SECRET_FILE = "client_secret.json"
APPLICATION_NAME = "Google Calendar API Python Quickstart"

# Japanese holiday calendar ID
HOLIDAY_CALENDAR_ID = "ja.japanese#holiday@group.v.calendar.google.com"


def is_holiday(service, date):
    """Check if the given date is a holiday.

    Args:
        service: Google Calendar API service object
        date: Date to check (datetime object)

    Returns:
        Boolean indicating if date is a holiday
    """
    # Convert to JST
    jst = pytz.timezone("Asia/Tokyo")
    date_jst = date.astimezone(jst)

    # Set time to midnight
    start_date = date_jst.replace(hour=0, minute=0, second=0, microsecond=0)
    end_date = start_date + datetime.timedelta(days=1)

    # Convert back to UTC for API
    start_str = start_date.astimezone(pytz.UTC).isoformat()
    end_str = end_date.astimezone(pytz.UTC).isoformat()

    # Query holiday calendar
    events_result = (
        service.events()
        .list(
            calendarId=HOLIDAY_CALENDAR_ID,
            timeMin=start_str,
            timeMax=end_str,
            singleEvents=True,
        )
        .execute()
    )

    events = events_result.get("items", [])
    return len(events) > 0


def get_credentials():
    """Gets valid user credentials from storage.

    If nothing has been stored, or if the stored credentials are invalid,
    the OAuth2 flow is completed to obtain the new credentials.

    Returns:
        Credentials, the obtained credential.
    """
    home_dir = os.path.expanduser("~")
    credential_dir = os.path.join(home_dir, ".credentials")
    if not os.path.exists(credential_dir):
        os.makedirs(credential_dir)
    credential_path = os.path.join(credential_dir, "calendar-python-quickstart.json")

    store = Storage(credential_path)
    credentials = store.get()
    if not credentials or credentials.invalid:
        flow = client.flow_from_clientsecrets(CLIENT_SECRET_FILE, SCOPES)
        flow.user_agent = APPLICATION_NAME
        if flags:
            credentials = tools.run_flow(flow, store, flags)
        else:  # Needed only for compatibility with Python 2.6
            credentials = tools.run(flow, store)
        print("Storing credentials to " + credential_path)
    return credentials


def find_available_slots(service, start_date, end_date, include_holidays=False, min_hours=1):
    """Find available time slots (minimum specified hours with 30 min buffer) during business hours (10:00-18:00) on weekdays.

    Args:
        service: Google Calendar API service object
        start_date: Start date to search from (datetime object)
        end_date: End date to search to (datetime object)
        include_holidays: Whether to include holidays in results (default: False)
        min_hours: Minimum duration in hours for available slots (default: 1)

    Returns:
        List of available time slots
    """
    jst = pytz.timezone("Asia/Tokyo")
    now_jst = datetime.datetime.now(jst)

    # Convert input dates to JST
    start_date_jst = start_date.replace(tzinfo=pytz.UTC).astimezone(jst)
    end_date_jst = end_date.replace(tzinfo=pytz.UTC).astimezone(jst)

    # If start_date is in the past, use current time instead
    if start_date_jst < now_jst:
        start_date_jst = now_jst

    # Get calendar events
    start_date_utc = start_date_jst.astimezone(pytz.UTC)
    end_date_utc = end_date_jst.astimezone(pytz.UTC)

    start_str = start_date_utc.isoformat()
    end_str = end_date_utc.isoformat()

    events_result = (
        service.events()
        .list(
            calendarId="primary",
            timeMin=start_str,
            timeMax=end_str,
            singleEvents=True,
            orderBy="startTime",
        )
        .execute()
    )
    events = events_result.get("items", [])

    # Create a list of busy periods
    busy_periods = []
    for event in events:
        start = event["start"].get("dateTime")
        end = event["end"].get("dateTime")

        # Skip all-day events
        if not start or not end:
            continue

        start_dt = date_parser.parse(start).astimezone(jst)
        end_dt = date_parser.parse(end).astimezone(jst)

        busy_periods.append((start_dt, end_dt))

    # Find available slots on weekdays between 10:00-18:00
    available_slots = []
    current_date = start_date_jst.replace(hour=0, minute=0, second=0, microsecond=0)

    # Adjust current_date to start of day
    if current_date.hour > 0 or current_date.minute > 0:
        current_date = current_date + datetime.timedelta(days=1)
        current_date = current_date.replace(hour=0, minute=0, second=0, microsecond=0)

    while current_date <= end_date_jst:
        # Check if it's a weekday (0=Monday, 6=Sunday)
        if current_date.weekday() < 5:  # Monday to Friday
            # Skip holidays unless specifically included
            if not include_holidays and is_holiday(service, current_date):
                current_date += datetime.timedelta(days=1)
                continue

            # Business hours 10:00-18:00 (but effective range is 10:30-17:30 due to buffer)
            day_start = current_date.replace(hour=10, minute=0, second=0, microsecond=0)
            day_end = current_date.replace(hour=18, minute=0, second=0, microsecond=0)

            # Apply 30 min buffer at start and end of business hours
            effective_day_start = day_start + datetime.timedelta(minutes=30)
            effective_day_end = day_end - datetime.timedelta(minutes=30)

            # Skip days in the past
            if day_end < now_jst:
                current_date += datetime.timedelta(days=1)
                continue

            # If current time is during business hours, start from current time
            if (
                now_jst > effective_day_start
                and now_jst < effective_day_end
                and current_date.date() == now_jst.date()
            ):
                effective_day_start = now_jst

            # Get busy periods for this day
            day_busy_periods = [
                (max(day_start, start), min(day_end, end))
                for start, end in busy_periods
                if start.date() == current_date.date()
                and end > day_start
                and start < day_end
            ]

            # Sort busy periods by start time
            day_busy_periods.sort(key=lambda x: x[0])

            # Find gaps between busy periods
            if not day_busy_periods:
                # Entire business day is free
                duration = (effective_day_end - effective_day_start).total_seconds() / 3600
                available_slots.append({
                    'start': effective_day_start,
                    'end': effective_day_end,
                    'duration': duration
                })
            else:
                # Check time before first meeting
                if day_busy_periods[0][0] > effective_day_start + datetime.timedelta(
                    hours=min_hours
                ):  # At least min_hours after effective start
                    gap_end = day_busy_periods[0][0] - datetime.timedelta(minutes=30)
                    duration = (gap_end - effective_day_start).total_seconds() / 3600
                    available_slots.append({
                        'start': effective_day_start,
                        'end': gap_end,
                        'duration': duration
                    })

                # Check between meetings
                for i in range(len(day_busy_periods) - 1):
                    gap_start = day_busy_periods[i][1] + datetime.timedelta(
                        minutes=30
                    )  # 30min buffer after
                    gap_end = day_busy_periods[i + 1][0] - datetime.timedelta(
                        minutes=30
                    )  # 30min buffer before

                    # If gap is at least the minimum required hours
                    if gap_end - gap_start >= datetime.timedelta(hours=min_hours):
                        duration = (gap_end - gap_start).total_seconds() / 3600
                        available_slots.append({
                            'start': gap_start,
                            'end': gap_end,
                            'duration': duration
                        })

                # Check time after last meeting
                if effective_day_end > day_busy_periods[-1][1] + datetime.timedelta(
                    hours=min_hours
                ):  # At least min_hours before effective end
                    gap_start = day_busy_periods[-1][1] + datetime.timedelta(minutes=30)
                    duration = (effective_day_end - gap_start).total_seconds() / 3600
                    available_slots.append({
                        'start': gap_start,
                        'end': effective_day_end,
                        'duration': duration
                    })

        current_date += datetime.timedelta(days=1)

    return available_slots


def format_output(slots, format='text', min_duration=1.0, include_holidays=False, show_total_hours=False, weekday_lang='ja'):
    """出力をフォーマット"""
    if format == 'json':
        return json.dumps({
            'slots': [
                {
                    'start': slot['start'].isoformat(),
                    'end': slot['end'].isoformat(),
                    'duration': slot['duration']
                }
                for slot in slots
            ],
            'total_hours': sum(slot['duration'] for slot in slots)
        })
    else:
        output = []
        output.append("Finding available time slots (weekdays, 10:00-18:00) of {}+ hours for the next 2 weeks".format(min_duration))
        if not include_holidays:
            output.append("Holidays are excluded. Use --include-holidays to include them.")
        output.append("Found {} available time slots:".format(len(slots)))
        
        # Format weekday based on language
        date_format = '%Y-%m-%d(%a) %H:%M' if weekday_lang == 'en' else '%Y-%m-%d(%a) %H:%M'
        
        for slot in slots:
            output.append("{} - {}".format(
                slot['start'].strftime(date_format),
                slot['end'].strftime('%H:%M')
            ))
        
        # Show total hours if requested
        if show_total_hours:
            output.append("\n合計空き時間: {}時間".format(sum(slot['duration'] for slot in slots)))
            
        return '\n'.join(output)


def main():
    """メイン処理"""
    parser = argparse.ArgumentParser(description='Google Calendarの予定を確認し、空き時間を探すツール')
    parser.add_argument('--format', '-f', choices=['text', 'json'], default='text', help='出力形式 (text/json)')
    parser.add_argument('--available-slots', '-a', nargs='?', const=1.0, type=float, help='空き時間を探す（最小時間を指定可能、デフォルト: 1.0時間）')
    parser.add_argument('--show-total-hours', '-t', action='store_true', help='空き時間の合計を表示する')
    parser.add_argument('--include-holidays', action='store_true', help='祝日を含める')
    parser.add_argument('--weekday-lang', '-w', default='ja', choices=['ja', 'en'], help='曜日の言語: ja (日本語) または en (英語)')
    args = parser.parse_args()

    if len(sys.argv) == 1:
        parser.print_help()
        return

    credentials = get_credentials()
    http = credentials.authorize(httplib2.Http())
    service = discovery.build("calendar", "v3", http=http)

    if args.available_slots is not None:
        now = datetime.datetime.utcnow()
        two_weeks_later = now + datetime.timedelta(days=14)
        slots = find_available_slots(service, now, two_weeks_later, include_holidays=args.include_holidays, min_hours=args.available_slots)
        print(format_output(
            slots, 
            format=args.format, 
            min_duration=args.available_slots, 
            include_holidays=args.include_holidays,
            show_total_hours=args.show_total_hours,
            weekday_lang=args.weekday_lang
        ))


if __name__ == "__main__":
    main()
