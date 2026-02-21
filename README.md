# YouTube Channel Report Generator

YouTube Data API v3 を使って、任意のYouTubeチャンネルの動画分析レポート（HTML）を自動生成するツールです。

## 機能

- チャンネルの最新動画を取得・分析
- 再生回数トレンドチャート（棒グラフ＋折れ線）
- いいね数トレンドチャート
- 人気動画ランキングテーブル（サムネイル・再生数・いいね数付き）
- レスポンシブ対応のダークテーマUI

## スクリーンショット

生成されるレポートの例：

- ヘッダー：チャンネル名、登録者数、総再生数
- チャート：Chart.js による再生数・いいね数の推移
- ランキング：再生数順の動画一覧（クリックでYouTubeへ遷移）

## 必要なもの

- Python 3.6+
- YouTube Data API v3 の APIキー（[Google Cloud Console](https://console.cloud.google.com/) で取得）

## 使い方

```bash
# 基本的な使い方
python youtube_report.py YOUR_API_KEY @channelhandle

# チャンネルURLで指定
python youtube_report.py YOUR_API_KEY "https://www.youtube.com/@cotenradio"

# チャンネルIDで指定
python youtube_report.py YOUR_API_KEY UCxxxxxxxxxxxxxxxxxxxxxxxx

# オプション: 動画数と出力ファイル名を指定
python youtube_report.py YOUR_API_KEY @channelhandle -n 50 -o my_report.html
```

## オプション

| 引数 | 説明 | デフォルト |
|------|------|-----------|
| `api_key` | YouTube Data API v3 のAPIキー | (必須) |
| `channel` | チャンネルID, @ハンドル, またはURL | (必須) |
| `-n`, `--num` | 取得する動画数 | 30 |
| `-o`, `--output` | 出力HTMLファイル名 | `youtube_report.html` |

## ライセンス

MIT License
