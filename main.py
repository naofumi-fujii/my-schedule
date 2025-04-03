# -*- coding: utf-8 -*-
"""
My Schedule - Google Calendarの空き時間検索ツール

このスクリプトはGoogle Calendarから予定を取得し、空き時間を検索するためのツールです。
平日の営業時間（10:00-18:00）内で、指定した最小時間以上の空き時間を見つけることができます。
"""
from __future__ import print_function
import httplib2
import os
import sys
import datetime
import json
from dateutil import parser as date_parser
import pytz
import argparse

from apiclient import discovery
from oauth2client import client
from oauth2client import tools
from oauth2client.file import Storage

# 定数定義
# Google API関連
SCOPES = "https://www.googleapis.com/auth/calendar.readonly"
CLIENT_SECRET_FILE = "client_secret.json"
APPLICATION_NAME = "Google Calendar API Python Quickstart"
CREDENTIALS_PATH = os.path.join(os.path.expanduser("~"), ".credentials", "calendar-python-quickstart.json")

# カレンダー関連
HOLIDAY_CALENDAR_ID = "ja.japanese#holiday@group.v.calendar.google.com"
PRIMARY_CALENDAR_ID = "primary"

# 時間関連
JST_TIMEZONE = "Asia/Tokyo"
BUSINESS_HOURS_START = 10  # 10:00
BUSINESS_HOURS_END = 18    # 18:00
BUFFER_MINUTES = 30        # 予定の前後のバッファー時間（分）
DEFAULT_MIN_HOURS = 1.0    # デフォルトの最小空き時間（時間）
DEFAULT_DAYS_AHEAD = 14    # デフォルトの検索期間（日）

# 引数解析のための共通パーサー設定
def setup_arg_parser():
    """コマンドライン引数パーサーを設定する"""
    parser = argparse.ArgumentParser(
        parents=[tools.argparser],
        description='Google Calendarの予定を確認し、空き時間を探すツール'
    )
    parser.add_argument(
        "--format", "-f",
        default="text",
        choices=["text", "json"],
        help="出力形式: text または json",
    )
    parser.add_argument(
        "--available-slots", "-a",
        nargs="?",
        const=DEFAULT_MIN_HOURS,
        type=float,
        help=f"営業時間内（{BUSINESS_HOURS_START}:00-{BUSINESS_HOURS_END}:00）で最小N時間の空き時間を探す（例: -a 2 で2時間以上）",
    )
    parser.add_argument(
        "--show-total-hours", "-t",
        action="store_true",
        help="空き時間の合計時間を表示する（--available-slotsと併用）",
    )
    parser.add_argument(
        "--weekday-lang", "-w",
        default="ja",
        choices=["ja", "en"],
        help="曜日の表示言語: ja（日本語）または en（英語）",
    )
    parser.add_argument(
        "--include-holidays",
        action="store_true",
        help="祝日を検索結果に含める（デフォルトでは除外）",
    )
    return parser


# タイムゾーン処理用のユーティリティ関数
def get_jst_timezone():
    """JSTタイムゾーンを取得する"""
    return pytz.timezone(JST_TIMEZONE)

def to_jst(dt):
    """日時をJSTタイムゾーンに変換する
    
    Args:
        dt: タイムゾーン情報を含むdatetimeオブジェクト、またはUTC想定のタイムゾーンなし日時
        
    Returns:
        JSTタイムゾーンのdatetimeオブジェクト
    """
    jst = get_jst_timezone()
    
    # タイムゾーン情報がない場合はUTCとして扱う
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=pytz.UTC)
        
    return dt.astimezone(jst)

def to_utc_str(dt):
    """日時をUTCのISO形式文字列に変換する
    
    Args:
        dt: 任意のタイムゾーンのdatetimeオブジェクト
        
    Returns:
        UTC ISO形式の文字列
    """
    # タイムゾーン情報がない場合はUTCとして扱う
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=pytz.UTC)
    else:
        dt = dt.astimezone(pytz.UTC)
        
    return dt.isoformat()

def get_day_start_end(date):
    """指定された日の開始と終了時刻を取得する
    
    Args:
        date: 任意のタイムゾーンのdatetimeオブジェクト
        
    Returns:
        (start, end): 日の開始時刻と終了時刻（JSTタイムゾーン）のタプル
    """
    date_jst = to_jst(date)
    start = date_jst.replace(hour=0, minute=0, second=0, microsecond=0)
    end = start + datetime.timedelta(days=1)
    return start, end

def get_business_hours(date):
    """指定された日の営業時間を取得する
    
    Args:
        date: 任意のタイムゾーンのdatetimeオブジェクト
        
    Returns:
        (start, end, effective_start, effective_end): 
            営業時間の開始・終了とバッファを適用した実効営業時間（すべてJSTタイムゾーン）
    """
    date_jst = to_jst(date)
    date_start = date_jst.replace(hour=0, minute=0, second=0, microsecond=0)
    
    # 営業時間
    day_start = date_start.replace(hour=BUSINESS_HOURS_START, minute=0)
    day_end = date_start.replace(hour=BUSINESS_HOURS_END, minute=0)
    
    # バッファを適用した実効営業時間
    effective_start = day_start + datetime.timedelta(minutes=BUFFER_MINUTES)
    effective_end = day_end - datetime.timedelta(minutes=BUFFER_MINUTES)
    
    return day_start, day_end, effective_start, effective_end

def is_holiday(service, date):
    """指定された日が祝日かどうかを判定する
    
    Args:
        service: Google Calendar API サービスオブジェクト
        date: 確認する日付（datetimeオブジェクト）
        
    Returns:
        祝日の場合はTrue、そうでない場合はFalse
    """
    # 指定された日の開始と終了を取得
    start_date, end_date = get_day_start_end(date)
    
    # API用にUTC ISO形式に変換
    start_str = to_utc_str(start_date)
    end_str = to_utc_str(end_date)
    
    # 祝日カレンダーを照会
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

def get_credentials(args=None):
    """Google APIの認証情報を取得する
    
    保存済みの認証情報がない場合や無効な場合は、OAuth2フローを実行して新しい認証情報を取得する。
    
    Args:
        args: 引数オブジェクト（OAuth2フローに使用）
        
    Returns:
        取得した認証情報
    """
    # 認証情報ディレクトリの作成
    credential_dir = os.path.dirname(CREDENTIALS_PATH)
    if not os.path.exists(credential_dir):
        os.makedirs(credential_dir)
    
    # 保存済みの認証情報を取得
    store = Storage(CREDENTIALS_PATH)
    credentials = store.get()
    
    # 認証情報がない場合や無効な場合は新しく取得
    if not credentials or credentials.invalid:
        flow = client.flow_from_clientsecrets(CLIENT_SECRET_FILE, SCOPES)
        flow.user_agent = APPLICATION_NAME
        
        if args:
            credentials = tools.run_flow(flow, store, args)
        else:
            credentials = tools.run(flow, store)
            
        print("認証情報を保存しました: {}".format(CREDENTIALS_PATH))
        
    return credentials


def get_calendar_events(service, start_date, end_date):
    """指定期間のカレンダーイベントを取得する
    
    Args:
        service: Google Calendar API サービスオブジェクト
        start_date: 検索開始日時（datetimeオブジェクト）
        end_date: 検索終了日時（datetimeオブジェクト）
        
    Returns:
        イベントリスト
    """
    # API用にUTC ISO形式に変換
    start_str = to_utc_str(start_date)
    end_str = to_utc_str(end_date)
    
    # イベント取得
    events_result = (
        service.events()
        .list(
            calendarId=PRIMARY_CALENDAR_ID,
            timeMin=start_str,
            timeMax=end_str,
            singleEvents=True,
            orderBy="startTime",
        )
        .execute()
    )
    
    return events_result.get("items", [])

def parse_busy_periods(events):
    """イベントリストから予定時間（ビジー期間）リストを作成する
    
    Args:
        events: Google Calendarイベントリスト
        
    Returns:
        (start, end)形式のタプルリスト（JSTタイムゾーン）
    """
    busy_periods = []
    
    for event in events:
        start = event["start"].get("dateTime")
        end = event["end"].get("dateTime")
        
        # 終日イベントをスキップ
        if not start or not end:
            continue
            
        # 日時をJSTに変換
        start_jst = to_jst(date_parser.parse(start))
        end_jst = to_jst(date_parser.parse(end))
        
        busy_periods.append((start_jst, end_jst))
        
    return busy_periods

def calculate_duration_hours(start, end):
    """開始時刻と終了時刻から時間単位の所要時間を計算する
    
    Args:
        start: 開始時刻（datetimeオブジェクト）
        end: 終了時刻（datetimeオブジェクト）
        
    Returns:
        時間単位の所要時間（float）
    """
    return (end - start).total_seconds() / 3600

def find_available_slots(service, start_date, end_date, include_holidays=False, min_hours=DEFAULT_MIN_HOURS):
    """営業時間内（平日10:00-18:00）で、指定した最小時間以上の空き時間を検索する
    
    Args:
        service: Google Calendar API サービスオブジェクト
        start_date: 検索開始日時（datetimeオブジェクト）
        end_date: 検索終了日時（datetimeオブジェクト）
        include_holidays: 祝日を含めるかどうか（デフォルト: False）
        min_hours: 最小空き時間（時間単位、デフォルト: 1時間）
        
    Returns:
        利用可能な時間枠のリスト（各要素はstart, end, durationを含む辞書）
    """
    # 現在時刻（JST）
    jst = get_jst_timezone()
    now_jst = datetime.datetime.now(jst)
    
    # 入力日時をJSTに変換
    start_date_jst = to_jst(start_date)
    end_date_jst = to_jst(end_date)
    
    # 開始日時が過去の場合は現在時刻を使用
    if start_date_jst < now_jst:
        start_date_jst = now_jst
        
    # カレンダーイベントを取得
    events = get_calendar_events(service, start_date_jst, end_date_jst)
    
    # 予定時間リストを作成
    busy_periods = parse_busy_periods(events)
    
    # 検索開始日を日の始めに調整
    current_date = start_date_jst.replace(hour=0, minute=0, second=0, microsecond=0)
    
    available_slots = []
    
    # 各日の空き時間を検索
    while current_date <= end_date_jst:
        # 平日（月〜金）のみ処理
        if current_date.weekday() < 5:
            # 祝日はスキップ（指定がない限り）
            if not include_holidays and is_holiday(service, current_date):
                current_date += datetime.timedelta(days=1)
                continue
                
            # 営業時間を取得
            day_start, day_end, effective_day_start, effective_day_end = get_business_hours(current_date)
            
            # 過去の日はスキップ
            if day_end < now_jst:
                current_date += datetime.timedelta(days=1)
                continue
                
            # 現在日時が営業時間内の場合、開始時間を現在時刻に調整
            if (now_jst > effective_day_start and 
                now_jst < effective_day_end and 
                current_date.date() == now_jst.date()):
                effective_day_start = now_jst
                
            # この日の予定を抽出
            day_busy_periods = [
                (max(day_start, start), min(day_end, end))
                for start, end in busy_periods
                if start.date() == current_date.date()
                and end > day_start
                and start < day_end
            ]
            
            # 開始時間でソート
            day_busy_periods.sort(key=lambda x: x[0])
            
            # 空き時間を検索
            if not day_busy_periods:
                # 予定がなければ1日すべて空き
                duration = calculate_duration_hours(effective_day_start, effective_day_end)
                available_slots.append({
                    'start': effective_day_start,
                    'end': effective_day_end,
                    'duration': duration
                })
            else:
                # 最初の予定より前の時間
                min_duration_timedelta = datetime.timedelta(hours=min_hours)
                if day_busy_periods[0][0] > effective_day_start + min_duration_timedelta:
                    # バッファを適用
                    gap_end = day_busy_periods[0][0] - datetime.timedelta(minutes=BUFFER_MINUTES)
                    duration = calculate_duration_hours(effective_day_start, gap_end)
                    available_slots.append({
                        'start': effective_day_start,
                        'end': gap_end,
                        'duration': duration
                    })
                    
                # 予定と予定の間の時間
                for i in range(len(day_busy_periods) - 1):
                    # バッファを適用
                    gap_start = day_busy_periods[i][1] + datetime.timedelta(minutes=BUFFER_MINUTES)
                    gap_end = day_busy_periods[i + 1][0] - datetime.timedelta(minutes=BUFFER_MINUTES)
                    
                    # 最小時間以上の空きがあるか確認
                    if gap_end - gap_start >= min_duration_timedelta:
                        duration = calculate_duration_hours(gap_start, gap_end)
                        available_slots.append({
                            'start': gap_start,
                            'end': gap_end,
                            'duration': duration
                        })
                        
                # 最後の予定より後の時間
                if effective_day_end > day_busy_periods[-1][1] + min_duration_timedelta:
                    # バッファを適用
                    gap_start = day_busy_periods[-1][1] + datetime.timedelta(minutes=BUFFER_MINUTES)
                    duration = calculate_duration_hours(gap_start, effective_day_end)
                    available_slots.append({
                        'start': gap_start,
                        'end': effective_day_end,
                        'duration': duration
                    })
                    
        # 次の日へ
        current_date += datetime.timedelta(days=1)
        
    return available_slots


def format_output_json(slots):
    """空き時間リストをJSON形式でフォーマットする
    
    Args:
        slots: 空き時間リスト
        
    Returns:
        JSON形式の文字列
    """
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

def format_output_text(slots, min_duration, include_holidays, show_total_hours, weekday_lang):
    """空き時間リストをテキスト形式でフォーマットする
    
    Args:
        slots: 空き時間リスト
        min_duration: 最小時間（時間単位）
        include_holidays: 祝日を含めるかどうか
        show_total_hours: 合計時間を表示するかどうか
        weekday_lang: 曜日の言語（'ja'または'en'）
        
    Returns:
        テキスト形式の文字列
    """
    output = []
    
    # ヘッダー
    output.append(
        "Finding available time slots (weekdays, {0}:00-{1}:00) of {2}+ hours for the next {3} days".format(
            BUSINESS_HOURS_START, BUSINESS_HOURS_END, min_duration, DEFAULT_DAYS_AHEAD
        )
    )
    
    # 祝日の扱いについて説明
    if not include_holidays:
        output.append("Holidays are excluded. Use --include-holidays to include them.")
        
    # 検索結果数
    output.append("Found {} available time slots:".format(len(slots)))
    
    # 日時フォーマットを言語に合わせて設定
    date_format = '%Y-%m-%d(%a) %H:%M' if weekday_lang == 'en' else '%Y-%m-%d(%a) %H:%M'
    
    # 各スロットを出力
    for slot in slots:
        output.append("{} - {}".format(
            slot['start'].strftime(date_format),
            slot['end'].strftime('%H:%M')
        ))
    
    # 合計時間の表示（オプション）
    if show_total_hours:
        total_hours = sum(slot['duration'] for slot in slots)
        output.append("\n合計空き時間: {:.2f}時間".format(total_hours))
        
    return '\n'.join(output)

def format_output(slots, format='text', min_duration=DEFAULT_MIN_HOURS, 
                 include_holidays=False, show_total_hours=False, weekday_lang='ja'):
    """空き時間リストを指定された形式でフォーマットする
    
    Args:
        slots: 空き時間リスト
        format: 出力形式（'text'または'json'）
        min_duration: 最小時間（時間単位）
        include_holidays: 祝日を含めるかどうか
        show_total_hours: 合計時間を表示するかどうか
        weekday_lang: 曜日の言語（'ja'または'en'）
        
    Returns:
        フォーマットされた文字列
    """
    if format == 'json':
        return format_output_json(slots)
    else:
        return format_output_text(
            slots, min_duration, include_holidays, show_total_hours, weekday_lang
        )

def get_calendar_service(args=None):
    """Google Calendar APIサービスを取得する
    
    Args:
        args: 引数オブジェクト（OAuth2フローに使用）
        
    Returns:
        Google Calendar APIサービスオブジェクト
    """
    credentials = get_credentials(args)
    http = credentials.authorize(httplib2.Http())
    return discovery.build("calendar", "v3", http=http)

def main():
    """メイン処理"""
    # 引数パーサーを設定
    parser = setup_arg_parser()
    args = parser.parse_args()
    
    # 引数がなければヘルプを表示して終了
    if len(sys.argv) == 1:
        parser.print_help()
        return
    
    # Google Calendar APIサービスを初期化
    service = get_calendar_service(args)
    
    # 空き時間検索処理
    if args.available_slots is not None:
        # 検索期間（現在から2週間後まで）
        now = datetime.datetime.now(pytz.UTC)
        end_date = now + datetime.timedelta(days=DEFAULT_DAYS_AHEAD)
        
        # 空き時間検索
        slots = find_available_slots(
            service, 
            now, 
            end_date, 
            include_holidays=args.include_holidays, 
            min_hours=args.available_slots
        )
        
        # 結果を出力
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
