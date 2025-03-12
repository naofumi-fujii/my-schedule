# my-schedule

A Python tool for displaying Google Calendar events and finding available time slots during business hours. You can view your schedule for the next two weeks and identify free time between meetings.

## Motivation
- I often find myself wondering about my availability when scheduling meetings, so I created this program to easily check my free time slots.

## Features

- Display Google Calendar events for the next 2 weeks
- Find available time slots during business hours (10:00-18:00 JST) on weekdays
- Calculate total available hours
- Output in both text and JSON formats
- Consider 30-minute buffers before and after meetings
- Show only time slots that are at least 1 hour long

## Installation

1. Clone the repository:
   ```bash
   git clone https://github.com/naofumi-fujii/my-schedule.git
   cd my-schedule
   ```

2. Install the required dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Set up Google Calendar API credentials:
   - Go to [Google Developers Console](https://console.developers.google.com/)
   - Create a new project and enable the Google Calendar API
   - Create credentials (OAuth client ID)
   - Download the credentials JSON file and save it as `client_secret.json` in the project directory

## Running Tests

```bash
# Run tests
pytest test_main.py

# Run tests with detailed output
pytest test_main.py -v
```

## Usage

### Basic Usage (Show upcoming events)
```bash
python main.py
```

### Find Available Time Slots
```bash
python main.py --available-slots
```

### Find Available Time Slots and Show Total Hours
```bash
python main.py --available-slots --show-total-hours
```

### Output in JSON Format
```bash
python main.py --format json
```

## Example Output

```
Finding available time slots (weekdays, 10:00-18:00) for the next 2 weeks
Found 15 available time slots:
2025-03-13(Thu) 10:30 - 12:00
2025-03-13(Thu) 13:30 - 17:30
2025-03-14(Fri) 10:30 - 15:00
...

Total available hours: 42.5 hours
```

## License

MIT License