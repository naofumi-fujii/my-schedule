# my-schedule

A Python tool to view Google Calendar events and find available time slots during business hours. The tool displays upcoming calendar events and can identify free time slots between meetings.

## Features

- View upcoming events from your Google Calendar for the next 2 weeks
- Find available time slots during business hours (10:00-18:00 JST) on weekdays
- Calculate total available hours
- Output in both text and JSON formats
- Considers 30-minute buffers before and after meetings
- Only shows time slots of 1 hour or more

## Installation

1. Clone the repository:
   ```bash
   git clone https://github.com/naofumi-fujii/my-schedule.git
   cd my-schedule
   ```

2. Install required dependencies:
   ```bash
   pip install --upgrade google-api-python-client oauth2client python-dateutil pytz
   ```

3. Set up Google Calendar API credentials:
   - Go to the [Google Developers Console](https://console.developers.google.com/)
   - Create a new project and enable the Google Calendar API
   - Create credentials (OAuth client ID)
   - Download the credentials JSON file and save it as `client_secret.json` in the project directory

## Usage

### Basic usage (view upcoming events)
```bash
python main.py
```

### Find available slots
```bash
python main.py --available-slots
```

### Find available slots and show total hours
```bash
python main.py --available-slots --show-total-hours
```

### Output in JSON format
```bash
python main.py --format json
```

## Example Output

```
Finding available time slots (weekdays, 10:00-18:00) for the next 2 weeks
Found 15 available time slots:
2025-03-13(木) 10:30 - 12:00 (1.5時間)
2025-03-13(木) 13:30 - 17:30 (4.0時間)
2025-03-14(金) 10:30 - 15:00 (4.5時間)
...

合計空き時間: 42.5時間
```

## License

MIT License