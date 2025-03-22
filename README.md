# My Schedule

Google Calendarの予定を確認し、空き時間を探すツールです。

## 機能

- Google Calendarの予定を表示
- 空き時間の検索（平日10:00-18:00）
- 祝日の除外（オプション）
- テキスト形式とJSON形式での出力

## セットアップ

### 必要条件

- Python 3.8以上
- Google Calendar APIの認証情報（`credentials.json`）

### インストール

1. 必要なパッケージをインストール:
```bash
pip install -r requirements.txt
```

2. Google Calendar APIの認証情報を設定:
   - Google Cloud Consoleでプロジェクトを作成
   - Calendar APIを有効化
   - 認証情報を作成し、`credentials.json`としてダウンロード
   - `credentials.json`をプロジェクトのルートディレクトリに配置

## 使い方

### ヘルプの表示
```bash
python main.py --help
```

### 空き時間の表示
```bash
# デフォルト（1時間以上の空き時間）
python main.py --available-slots

# 2時間以上の空き時間をJSON形式で表示
python main.py --available-slots 2 --format json

# 祝日を含めて表示
python main.py --available-slots --include-holidays
```

### 予定の表示
```bash
# テキスト形式で表示
python main.py

# JSON形式で表示
python main.py --format json

# 祝日を含めて表示
python main.py --include-holidays
```

## オプション

- `--format`: 出力形式を指定（text/json）
- `--available-slots`: 空き時間を探す
- `--include-holidays`: 祝日を含める

## 出力形式

### テキスト形式
```
Finding available time slots (weekdays, 10:00-18:00) of 1.0+ hours for the next 2 weeks
Holidays are excluded. Use --include-holidays to include them.
Found 8 available time slots:
2025-03-24(月) 12:30 - 16:30
2025-03-26(水) 14:25 - 15:30
...

合計空き時間: 25.4時間
```

### JSON形式
```json
{
  "slots": [
    {
      "start": "2025-03-24T12:30:00+09:00",
      "end": "2025-03-24T16:30:00+09:00",
      "duration": 4.0
    },
    ...
  ],
  "total_hours": 25.42
}
```

## 開発

### テストの実行
```bash
python -m pytest test_main.py -v
```

### コードの品質管理
```bash
# コードのフォーマット
black main.py test_main.py

# リンター
flake8 main.py test_main.py
```

## License

MIT License