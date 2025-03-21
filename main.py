from __future__ import print_function
import httplib2
import os

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
                available_slots.append((effective_day_start, effective_day_end))
            else:
                # Check time before first meeting
                if day_busy_periods[0][0] > effective_day_start + datetime.timedelta(
                    hours=min_hours
                ):  # At least min_hours after effective start
                    available_slots.append(
                        (
                            effective_day_start,
                            day_busy_periods[0][0] - datetime.timedelta(minutes=30),
                        )
                    )

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
                        available_slots.append((gap_start, gap_end))

                # Check time after last meeting
                if effective_day_end > day_busy_periods[-1][1] + datetime.timedelta(
                    hours=min_hours
                ):  # At least min_hours before effective end
                    available_slots.append(
                        (
                            day_busy_periods[-1][1] + datetime.timedelta(minutes=30),
                            effective_day_end,
                        )
                    )

        current_date += datetime.timedelta(days=1)

    return available_slots


def main():
    """Shows basic usage of the Google Calendar API.

    Creates a Google Calendar API service object and outputs events for the next
    2 weeks on the user's calendar.
    """
    # Parse arguments when main is called
    global flags
    if flags is None:
        flags = parser.parse_args()

    # If no arguments are provided, print help and exit
    if len(vars(flags)) == 0 or (getattr(flags, "available_slots", False) is False and
        not getattr(flags, "include_holidays", False) and 
        getattr(flags, "format", "text") == "text" and 
        getattr(flags, "weekday_lang", "ja") == "ja"):
        parser.print_help()
        return

    credentials = get_credentials()
    http = credentials.authorize(httplib2.Http())
    service = discovery.build("calendar", "v3", http=http)

    now = datetime.datetime.utcnow()
    two_weeks_later = now + datetime.timedelta(days=14)

    now_str = now.isoformat() + "Z"  # 'Z' indicates UTC time
    two_weeks_later_str = two_weeks_later.isoformat() + "Z"

    # Handle available slots option
    if getattr(flags, "available_slots", False) is not False:
        include_holidays = getattr(flags, "include_holidays", False)
        min_hours = float(getattr(flags, "available_slots", 1))
        print(
            f"Finding available time slots (weekdays, 10:00-18:00) of {min_hours}+ hours for the next 2 weeks"
        )
        if not include_holidays:
            print("Holidays are excluded. Use --include-holidays to include them.")

        available_slots = find_available_slots(
            service, now, two_weeks_later, include_holidays, min_hours
        )

        output_format = getattr(flags, "format", "text")
        jst = pytz.timezone("Asia/Tokyo")

        if not available_slots:
            if output_format == "json":
                print(json.dumps({"message": "No available time slots found."}))
            else:
                print("No available time slots found.")
        else:
            if output_format == "json":
                json_slots = []
                total_minutes = 0

                for start, end in available_slots:
                    # Calculate duration
                    duration_minutes = int((end - start).total_seconds() / 60)
                    total_minutes += duration_minutes

                    # Format as JSON
                    # Get day of week in Japanese or English based on setting
                    weekday_ja = ["月", "火", "水", "木", "金", "土", "日"]
                    weekday_en = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]

                    if getattr(flags, "weekday_lang", "ja") == "ja":
                        weekday_display = weekday_ja[start.weekday()]
                    else:
                        weekday_display = weekday_en[start.weekday()]

                    json_slots.append(
                        {
                            "start": {
                                "date": start.strftime("%Y-%m-%d"),
                                "time": start.strftime("%H:%M"),
                                "formatted": start.strftime("%Y-%m-%d %H:%M"),
                                "weekday": weekday_display,
                            },
                            "end": {
                                "date": end.strftime("%Y-%m-%d"),
                                "time": end.strftime("%H:%M"),
                                "formatted": end.strftime("%Y-%m-%d %H:%M"),
                                "weekday": weekday_display,
                            },
                            "duration_minutes": duration_minutes,
                        }
                    )

                result = {"available_slots": json_slots}

                # Add total hours if requested
                if getattr(flags, "show_total_hours", False):
                    result["total_hours"] = round(total_minutes / 60, 1)
                    result["total_minutes"] = total_minutes

                print(json.dumps(result, ensure_ascii=False, indent=2))
            else:
                # Text format
                print(f"Found {len(available_slots)} available time slots:")

                # Calculate total duration if needed
                total_minutes = 0

                for start, end in available_slots:
                    duration_minutes = int((end - start).total_seconds() / 60)
                    total_minutes += duration_minutes
                    # Get day of week in Japanese or English based on setting
                    weekday_ja = ["月", "火", "水", "木", "金", "土", "日"]
                    weekday_en = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]

                    if getattr(flags, "weekday_lang", "ja") == "ja":
                        weekday_display = weekday_ja[start.weekday()]
                    else:
                        weekday_display = weekday_en[start.weekday()]

                    # Always show date, time without individual slot duration
                    print(
                        f"{start.strftime('%Y-%m-%d')}({weekday_display}) {start.strftime('%H:%M')} - {end.strftime('%H:%M')}"
                    )

                # Show total hours if requested
                if getattr(flags, "show_total_hours", False):
                    total_hours = total_minutes / 60
                    if getattr(flags, "weekday_lang", "ja") == "ja":
                        print(f"\n合計空き時間: {total_hours:.1f}時間")
                    else:
                        print(f"\nTotal available hours: {total_hours:.1f} hours")

        return

    # Otherwise show the calendar events
    include_holidays = getattr(flags, "include_holidays", False)
    print("Getting events for the next 2 weeks")
    if not include_holidays:
        print("Holidays are excluded. Use --include-holidays to include them.")

    eventsResult = (
        service.events()
        .list(
            calendarId="primary",
            timeMin=now_str,
            timeMax=two_weeks_later_str,
            singleEvents=True,
            orderBy="startTime",
        )
        .execute()
    )
    events = eventsResult.get("items", [])

    # Filter out events on holidays if needed
    if not include_holidays:
        filtered_events = []
        for event in events:
            # Get event start date
            start_str = event["start"].get("dateTime", event["start"].get("date"))

            # Parse the date
            if "T" in start_str:  # dateTime format
                event_date = date_parser.parse(start_str)
            else:  # date format
                event_date = datetime.datetime.strptime(start_str, "%Y-%m-%d")
                event_date = datetime.datetime.combine(
                    event_date.date(), datetime.time(0, 0, 0, tzinfo=pytz.UTC)
                )

            # Skip events on holidays
            if not is_holiday(service, event_date):
                filtered_events.append(event)

        events = filtered_events

    jst = pytz.timezone("Asia/Tokyo")
    output_format = getattr(flags, "format", "text")  # デフォルトはテキスト形式

    if not events:
        if output_format == "json":
            print(json.dumps({"message": "No upcoming events found."}))
        else:
            print("No upcoming events found.")
    else:
        if output_format == "json":
            # JSON形式で出力する配列を準備
            json_events = []

            for event in events:
                # イベントの開始・終了時間を取得
                start_str = event["start"].get("dateTime", event["start"].get("date"))
                end_str = event["end"].get("dateTime", event["end"].get("date"))

                # 日時をパースして整形（日本時間に変換）
                if "T" in start_str:  # dateTimeの場合
                    start_dt = date_parser.parse(start_str)
                    start_dt_jst = start_dt.astimezone(jst)
                    start_formatted = start_dt_jst.strftime("%Y-%m-%d %H:%M")
                    start_date = start_dt_jst.strftime("%Y-%m-%d")
                    start_time = start_dt_jst.strftime("%H:%M")
                else:  # dateのみの場合
                    start_formatted = start_str
                    start_date = start_str
                    start_time = None

                if "T" in end_str:  # dateTimeの場合
                    end_dt = date_parser.parse(end_str)
                    end_dt_jst = end_dt.astimezone(jst)
                    end_formatted = end_dt_jst.strftime("%Y-%m-%d %H:%M")
                    end_date = end_dt_jst.strftime("%Y-%m-%d")
                    end_time = end_dt_jst.strftime("%H:%M")
                else:  # dateのみの場合
                    end_formatted = end_str
                    end_date = end_str
                    end_time = None

                # JSONオブジェクトを作成
                event_json = {
                    "summary": event.get("summary", ""),
                    "start": {
                        "date": start_date,
                        "time": start_time,
                        "formatted": start_formatted,
                    },
                    "end": {
                        "date": end_date,
                        "time": end_time,
                        "formatted": end_formatted,
                    },
                    "location": event.get("location", ""),
                    "description": event.get("description", ""),
                    "htmlLink": event.get("htmlLink", ""),
                }

                json_events.append(event_json)

            # JSON形式で出力
            print(json.dumps({"events": json_events}, ensure_ascii=False, indent=2))
        else:
            # テキスト形式で出力
            for event in events:
                start_str = event["start"].get("dateTime", event["start"].get("date"))
                end_str = event["end"].get("dateTime", event["end"].get("date"))

                # 日時をパースして整形（日本時間に変換）
                if "T" in start_str:  # dateTimeの場合
                    start_dt = date_parser.parse(start_str)
                    start_dt_jst = start_dt.astimezone(jst)
                    start_formatted = start_dt_jst.strftime("%Y-%m-%d %H:%M")
                else:  # dateのみの場合
                    start_formatted = start_str

                if "T" in end_str:  # dateTimeの場合
                    end_dt = date_parser.parse(end_str)
                    end_dt_jst = end_dt.astimezone(jst)
                    end_formatted = end_dt_jst.strftime("%Y-%m-%d %H:%M")
                else:  # dateのみの場合
                    end_formatted = end_str

                print(
                    f"開始: {start_formatted} - 終了: {end_formatted} | {event['summary']}"
                )


if __name__ == "__main__":
    main()
