# my-schedule

Googleカレンダーのイベントを表示し、営業時間内の空き時間を見つけるためのPythonツールです。今後2週間の予定を表示したり、ミーティングの間の空き時間を特定したりすることができます。

## 動機
- 会議などの日程を調整する際に、いつ空いてるんだっけ...ということが多々ありプログラムで確認できると便利だなと思って書きました。(主にAIが

## 特徴

- Googleカレンダーの今後2週間のイベントを表示
- 平日の営業時間（10:00-18:00 JST）内の空き時間を検索
- 利用可能な合計時間を計算
- テキスト形式とJSON形式の両方で出力可能
- ミーティングの前後に30分のバッファを考慮
- 1時間以上の空き時間のみを表示

## インストール方法

1. リポジトリをクローン:
   ```bash
   git clone https://github.com/naofumi-fujii/my-schedule.git
   cd my-schedule
   ```

2. 必要な依存関係をインストール:
   ```bash
   pip install --upgrade google-api-python-client oauth2client python-dateutil pytz
   ```

3. Google Calendar APIの認証情報を設定:
   - [Google Developers Console](https://console.developers.google.com/)にアクセス
   - 新しいプロジェクトを作成し、Google Calendar APIを有効化
   - 認証情報（OAuthクライアントID）を作成
   - 認証情報JSONファイルをダウンロードし、プロジェクトディレクトリに`client_secret.json`として保存

## 使用方法

### 基本的な使い方（今後のイベントを表示）
```bash
python main.py
```

### 空き時間を検索
```bash
python main.py --available-slots
```

### 空き時間を検索して合計時間を表示
```bash
python main.py --available-slots --show-total-hours
```

### JSON形式で出力
```bash
python main.py --format json
```

## 出力例

```
Finding available time slots (weekdays, 10:00-18:00) for the next 2 weeks
Found 15 available time slots:
2025-03-13(木) 10:30 - 12:00 (1.5時間)
2025-03-13(木) 13:30 - 17:30 (4.0時間)
2025-03-14(金) 10:30 - 15:00 (4.5時間)
...

合計空き時間: 42.5時間
```

## ライセンス

MIT License
