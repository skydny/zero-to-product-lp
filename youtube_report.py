#!/usr/bin/env python3
"""
YouTube Channel Report Generator
指定チャンネルの最新30本の動画情報を取得し、HTMLレポートを生成する
"""

import argparse
import json
import sys
from datetime import datetime
from urllib.request import urlopen, Request
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from html import escape

API_BASE = "https://www.googleapis.com/youtube/v3"


def api_get(endpoint, params):
    """YouTube Data API v3 にGETリクエストを送る"""
    url = f"{API_BASE}/{endpoint}?{urlencode(params)}"
    req = Request(url)
    try:
        with urlopen(req) as resp:
            return json.loads(resp.read().decode())
    except HTTPError as e:
        body = e.read().decode()
        print(f"API Error ({e.code}): {body}", file=sys.stderr)
        sys.exit(1)
    except URLError as e:
        print(f"Network Error: {e.reason}", file=sys.stderr)
        sys.exit(1)


def resolve_channel_id(api_key, channel_input):
    """チャンネルIDを解決する（ハンドル名・カスタムURL・IDに対応）"""
    # 既にチャンネルIDの形式 (UC...)
    if channel_input.startswith("UC") and len(channel_input) == 24:
        return channel_input

    # URLからの抽出
    handle = None
    if "youtube.com" in channel_input:
        if "/@" in channel_input:
            handle = channel_input.split("/@")[1].split("/")[0].split("?")[0]
        elif "/channel/" in channel_input:
            return channel_input.split("/channel/")[1].split("/")[0].split("?")[0]

    # @ハンドル
    if channel_input.startswith("@"):
        handle = channel_input[1:]
    elif handle is None:
        handle = channel_input

    # forHandle で検索
    data = api_get("channels", {
        "key": api_key,
        "forHandle": handle,
        "part": "id",
    })
    if data.get("items"):
        return data["items"][0]["id"]

    # search で検索（フォールバック）
    data = api_get("search", {
        "key": api_key,
        "q": channel_input,
        "type": "channel",
        "part": "id",
        "maxResults": 1,
    })
    if data.get("items"):
        return data["items"][0]["id"]["channelId"]

    print(f"チャンネルが見つかりません: {channel_input}", file=sys.stderr)
    sys.exit(1)


def get_channel_info(api_key, channel_id):
    """チャンネル情報を取得"""
    data = api_get("channels", {
        "key": api_key,
        "id": channel_id,
        "part": "snippet,contentDetails,statistics",
    })
    if not data.get("items"):
        print("チャンネル情報の取得に失敗しました", file=sys.stderr)
        sys.exit(1)
    return data["items"][0]


def get_latest_videos(api_key, channel_id, max_results=30):
    """チャンネルの最新動画を取得"""
    # search APIで最新動画のIDを取得
    video_ids = []
    page_token = None
    while len(video_ids) < max_results:
        params = {
            "key": api_key,
            "channelId": channel_id,
            "part": "id",
            "order": "date",
            "type": "video",
            "maxResults": min(50, max_results - len(video_ids)),
        }
        if page_token:
            params["pageToken"] = page_token
        data = api_get("search", params)
        for item in data.get("items", []):
            video_ids.append(item["id"]["videoId"])
        page_token = data.get("nextPageToken")
        if not page_token:
            break

    video_ids = video_ids[:max_results]
    if not video_ids:
        print("動画が見つかりませんでした", file=sys.stderr)
        sys.exit(1)

    # videos APIで詳細情報を取得（50件ずつ）
    videos = []
    for i in range(0, len(video_ids), 50):
        chunk = video_ids[i:i+50]
        data = api_get("videos", {
            "key": api_key,
            "id": ",".join(chunk),
            "part": "snippet,statistics",
        })
        for item in data.get("items", []):
            snippet = item["snippet"]
            stats = item.get("statistics", {})
            videos.append({
                "id": item["id"],
                "title": snippet["title"],
                "publishedAt": snippet["publishedAt"],
                "thumbnail": snippet["thumbnails"].get("medium", snippet["thumbnails"]["default"])["url"],
                "viewCount": int(stats.get("viewCount", 0)),
                "likeCount": int(stats.get("likeCount", 0)),
                "commentCount": int(stats.get("commentCount", 0)),
            })

    # 投稿日順（古い→新しい）でソート
    videos.sort(key=lambda v: v["publishedAt"])
    return videos


def generate_html(channel_info, videos):
    """HTMLレポートを生成"""
    channel_name = escape(channel_info["snippet"]["title"])
    channel_thumb = channel_info["snippet"]["thumbnails"]["default"]["url"]
    sub_count = int(channel_info["statistics"].get("subscriberCount", 0))
    total_views = int(channel_info["statistics"].get("viewCount", 0))

    # ランキング用（再生回数降順）
    ranked = sorted(videos, key=lambda v: v["viewCount"], reverse=True)

    # グラフ用データ（投稿日順）
    labels_json = json.dumps([v["publishedAt"][:10] for v in videos], ensure_ascii=False)
    views_json = json.dumps([v["viewCount"] for v in videos])
    likes_json = json.dumps([v["likeCount"] for v in videos])
    titles_json = json.dumps([v["title"] for v in videos], ensure_ascii=False)

    # ランキングテーブルHTML
    ranking_rows = ""
    for i, v in enumerate(ranked, 1):
        medal = ""
        if i == 1:
            medal = '<span style="font-size:1.4em">&#x1F947;</span> '
        elif i == 2:
            medal = '<span style="font-size:1.4em">&#x1F948;</span> '
        elif i == 3:
            medal = '<span style="font-size:1.4em">&#x1F949;</span> '

        ranking_rows += f"""
        <tr class="rank-row" onclick="window.open('https://www.youtube.com/watch?v={v['id']}','_blank')">
          <td class="rank-num">{medal}{i}</td>
          <td class="rank-thumb"><img src="{v['thumbnail']}" alt="" loading="lazy"></td>
          <td class="rank-title">{escape(v['title'])}</td>
          <td class="rank-stat">{v['viewCount']:,}</td>
          <td class="rank-stat">{v['likeCount']:,}</td>
          <td class="rank-date">{v['publishedAt'][:10]}</td>
        </tr>"""

    now = datetime.now().strftime("%Y-%m-%d %H:%M")

    html = f"""<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{channel_name} - YouTube Channel Report</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4"></script>
<style>
  :root {{
    --bg: #0f0f0f;
    --card: #1a1a2e;
    --card2: #16213e;
    --accent: #5bc0eb;
    --accent2: #1a6fb5;
    --text: #eaeaea;
    --text2: #a0a0b0;
    --gold: #ffd700;
    --silver: #c0c0c0;
    --bronze: #cd7f32;
  }}
  * {{ margin: 0; padding: 0; box-sizing: border-box; }}
  body {{
    background: var(--bg);
    color: var(--text);
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
    line-height: 1.6;
  }}
  .container {{ max-width: 1200px; margin: 0 auto; padding: 20px; }}

  /* Header */
  .header {{
    background: linear-gradient(135deg, var(--card) 0%, var(--card2) 100%);
    border-radius: 16px;
    padding: 32px;
    margin-bottom: 24px;
    display: flex;
    align-items: center;
    gap: 24px;
    border: 1px solid rgba(91,192,235,0.2);
  }}
  .header img {{
    width: 80px; height: 80px; border-radius: 50%;
    border: 3px solid var(--accent);
  }}
  .header h1 {{ font-size: 1.8em; }}
  .header .meta {{ color: var(--text2); font-size: 0.95em; margin-top: 4px; }}
  .stats-bar {{
    display: flex; gap: 24px; margin-top: 12px; flex-wrap: wrap;
  }}
  .stat-chip {{
    background: rgba(91,192,235,0.15);
    border: 1px solid rgba(91,192,235,0.3);
    border-radius: 8px;
    padding: 6px 16px;
    font-size: 0.9em;
  }}
  .stat-chip strong {{ color: var(--accent); }}

  /* Section */
  .section {{
    background: var(--card);
    border-radius: 16px;
    padding: 28px;
    margin-bottom: 24px;
    border: 1px solid rgba(255,255,255,0.05);
  }}
  .section h2 {{
    font-size: 1.3em;
    margin-bottom: 20px;
    padding-bottom: 12px;
    border-bottom: 2px solid var(--accent);
    display: inline-block;
  }}

  /* Chart */
  .chart-container {{
    position: relative;
    height: 400px;
    width: 100%;
  }}

  /* Ranking Table */
  .ranking-table {{
    width: 100%;
    border-collapse: collapse;
  }}
  .ranking-table th {{
    text-align: left;
    padding: 12px 8px;
    color: var(--text2);
    font-size: 0.85em;
    text-transform: uppercase;
    letter-spacing: 0.5px;
    border-bottom: 1px solid rgba(255,255,255,0.1);
  }}
  .rank-row {{
    cursor: pointer;
    transition: background 0.2s;
  }}
  .rank-row:hover {{
    background: rgba(91,192,235,0.1);
  }}
  .rank-row td {{
    padding: 10px 8px;
    border-bottom: 1px solid rgba(255,255,255,0.04);
    vertical-align: middle;
  }}
  .rank-num {{
    font-weight: 700;
    font-size: 1.1em;
    width: 60px;
    text-align: center;
  }}
  .rank-thumb {{
    width: 120px;
  }}
  .rank-thumb img {{
    width: 110px;
    border-radius: 6px;
  }}
  .rank-title {{
    font-weight: 500;
    max-width: 400px;
  }}
  .rank-stat {{
    text-align: right;
    font-variant-numeric: tabular-nums;
    white-space: nowrap;
  }}
  .rank-date {{
    color: var(--text2);
    white-space: nowrap;
  }}
  .rank-row:nth-child(1) .rank-num {{ color: var(--gold); }}
  .rank-row:nth-child(2) .rank-num {{ color: var(--silver); }}
  .rank-row:nth-child(3) .rank-num {{ color: var(--bronze); }}

  .footer {{
    text-align: center;
    color: var(--text2);
    font-size: 0.8em;
    padding: 20px 0;
  }}

  @media (max-width: 768px) {{
    .header {{ flex-direction: column; text-align: center; }}
    .stats-bar {{ justify-content: center; }}
    .chart-container {{ height: 300px; }}
    .rank-thumb {{ display: none; }}
    .rank-title {{ max-width: 200px; font-size: 0.9em; }}
  }}
</style>
</head>
<body>
<div class="container">

  <!-- Header -->
  <div class="header">
    <img src="{channel_thumb}" alt="{channel_name}">
    <div>
      <h1>{channel_name}</h1>
      <div class="meta">YouTube Channel Analytics Report</div>
      <div class="stats-bar">
        <div class="stat-chip">Subscribers: <strong>{sub_count:,}</strong></div>
        <div class="stat-chip">Total Views: <strong>{total_views:,}</strong></div>
        <div class="stat-chip">Analyzed: <strong>{len(videos)} videos</strong></div>
      </div>
    </div>
  </div>

  <!-- View Count Trend -->
  <div class="section">
    <h2>View Count Trend</h2>
    <div class="chart-container">
      <canvas id="viewChart"></canvas>
    </div>
  </div>

  <!-- Like Count Trend -->
  <div class="section">
    <h2>Like Count Trend</h2>
    <div class="chart-container">
      <canvas id="likeChart"></canvas>
    </div>
  </div>

  <!-- Ranking -->
  <div class="section">
    <h2>Popular Videos Ranking</h2>
    <div style="overflow-x:auto;">
      <table class="ranking-table">
        <thead>
          <tr>
            <th>Rank</th>
            <th>Thumbnail</th>
            <th>Title</th>
            <th style="text-align:right">Views</th>
            <th style="text-align:right">Likes</th>
            <th>Published</th>
          </tr>
        </thead>
        <tbody>{ranking_rows}
        </tbody>
      </table>
    </div>
  </div>

  <div class="footer">
    Generated at {now} &mdash; YouTube Channel Report Generator
  </div>

</div>

<script>
const labels = {labels_json};
const views = {views_json};
const likes = {likes_json};
const titles = {titles_json};

const commonOptions = {{
  responsive: true,
  maintainAspectRatio: false,
  interaction: {{
    mode: 'index',
    intersect: false,
  }},
  plugins: {{
    tooltip: {{
      callbacks: {{
        title: (items) => titles[items[0].dataIndex],
        label: (item) => item.dataset.label + ': ' + item.raw.toLocaleString(),
      }},
      backgroundColor: 'rgba(26,26,46,0.95)',
      titleFont: {{ size: 13 }},
      bodyFont: {{ size: 12 }},
      padding: 12,
      cornerRadius: 8,
    }},
    legend: {{
      labels: {{ color: '#eaeaea' }},
    }},
  }},
  scales: {{
    x: {{
      ticks: {{ color: '#a0a0b0', maxRotation: 45, font: {{ size: 10 }} }},
      grid: {{ color: 'rgba(255,255,255,0.05)' }},
    }},
    y: {{
      ticks: {{
        color: '#a0a0b0',
        callback: (v) => v >= 1e6 ? (v/1e6).toFixed(1)+'M' : v >= 1e3 ? (v/1e3).toFixed(0)+'K' : v,
      }},
      grid: {{ color: 'rgba(255,255,255,0.05)' }},
    }},
  }},
}};

new Chart(document.getElementById('viewChart'), {{
  type: 'bar',
  data: {{
    labels,
    datasets: [{{
      label: 'Views',
      data: views,
      backgroundColor: 'rgba(91,192,235,0.6)',
      borderColor: 'rgba(91,192,235,1)',
      borderWidth: 1,
      borderRadius: 4,
    }}, {{
      label: 'Trend',
      data: views,
      type: 'line',
      borderColor: '#1a6fb5',
      borderWidth: 2,
      pointRadius: 3,
      pointBackgroundColor: '#1a6fb5',
      tension: 0.3,
      fill: false,
    }}],
  }},
  options: commonOptions,
}});

new Chart(document.getElementById('likeChart'), {{
  type: 'line',
  data: {{
    labels,
    datasets: [{{
      label: 'Likes',
      data: likes,
      borderColor: '#7ec8e3',
      backgroundColor: 'rgba(126,200,227,0.15)',
      borderWidth: 2,
      pointRadius: 4,
      pointBackgroundColor: '#7ec8e3',
      tension: 0.3,
      fill: true,
    }}],
  }},
  options: commonOptions,
}});
</script>
</body>
</html>"""
    return html


def main():
    parser = argparse.ArgumentParser(
        description="YouTube チャンネルの動画レポートを生成する",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用例:
  python youtube_report.py YOUR_API_KEY @channelhandle
  python youtube_report.py YOUR_API_KEY UCxxxxxxxxxxxxxxxxxxxxxxxx
  python youtube_report.py YOUR_API_KEY "https://www.youtube.com/@handle"
  python youtube_report.py YOUR_API_KEY @handle -n 50 -o my_report.html
        """,
    )
    parser.add_argument("api_key", help="YouTube Data API v3 のAPIキー")
    parser.add_argument("channel", help="チャンネルID, @ハンドル, またはURL")
    parser.add_argument("-n", "--num", type=int, default=30, help="取得する動画数 (default: 30)")
    parser.add_argument("-o", "--output", default="youtube_report.html", help="出力ファイル名 (default: youtube_report.html)")
    args = parser.parse_args()

    print(f"[1/4] チャンネルIDを解決中...")
    channel_id = resolve_channel_id(args.api_key, args.channel)
    print(f"       Channel ID: {channel_id}")

    print(f"[2/4] チャンネル情報を取得中...")
    channel_info = get_channel_info(args.api_key, channel_id)
    print(f"       Channel: {channel_info['snippet']['title']}")

    print(f"[3/4] 最新 {args.num} 本の動画情報を取得中...")
    videos = get_latest_videos(args.api_key, channel_id, args.num)
    print(f"       取得完了: {len(videos)} 本")

    print(f"[4/4] HTMLレポートを生成中...")
    html = generate_html(channel_info, videos)
    with open(args.output, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"       完了! -> {args.output}")


if __name__ == "__main__":
    main()
