#!/usr/bin/env python3
"""
Send a Feishu (Lark) group bot webhook notification with the daily update link.

Environment variables:
  FEISHU_WEBHOOK_URL - Feishu bot webhook URL (required)
  SITE_URL            - The base URL of the GitHub Pages site (required)
"""

import os
import sys
import json
import requests
from datetime import datetime, timezone, timedelta

BJ_TZ = timezone(timedelta(hours=8))

WEBHOOK_URL = os.environ.get("FEISHU_WEBHOOK_URL", "")
SITE_URL = os.environ.get("SITE_URL", "").rstrip("/")


def send_notification(practice_title=None, news_titles=None):
    """Send a Feishu bot message with today's update info."""
    if not WEBHOOK_URL:
        print("FEISHU_WEBHOOK_URL not set, skipping notification.")
        return False

    if not SITE_URL:
        print("SITE_URL not set, skipping notification.")
        return False

    now = datetime.now(BJ_TZ)
    date_str = now.strftime("%Y-%m-%d")
    date_display = now.strftime("%m月%d日")

    # Build message content
    lines = []
    lines.append(f"📅 {date_display} 每日英语练习已更新！\n")

    if practice_title:
        lines.append(f"📝 口语练习: {practice_title}")
        lines.append(f"   {SITE_URL}/english-practice-{date_str}.html\n")

    if news_titles:
        lines.append(f"📰 英语新闻:")
        for title in news_titles:
            lines.append(f"   • {title}")
        lines.append(f"   {SITE_URL}/english-news-{date_str}.html\n")

    lines.append(f"🏠 目录页: {SITE_URL}/")
    lines.append("\n🔊 全部附带微软神经网络语音朗读，支持语速调节和逐句高亮。")

    content = "\n".join(lines)

    payload = {
        "msg_type": "text",
        "content": {
            "text": content
        }
    }

    try:
        resp = requests.post(
            WEBHOOK_URL,
            headers={"Content-Type": "application/json"},
            data=json.dumps(payload),
            timeout=10
        )
        result = resp.json()
        if result.get("StatusCode") == 0 or result.get("code") == 0 or resp.status_code == 200:
            print("Feishu notification sent successfully!")
            return True
        else:
            print(f"Feishu notification failed: {result}")
            return False
    except Exception as e:
        print(f"Feishu notification error: {e}")
        return False


def main():
    # Read generated files to get titles
    script_dir = os.path.dirname(os.path.abspath(__file__))

    practice_title = None
    practice_path = os.path.join(script_dir, "article-today.json")
    if os.path.exists(practice_path):
        try:
            with open(practice_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            practice_title = data.get("title", "")
        except Exception:
            pass

    news_titles = []
    news_path = os.path.join(script_dir, "news-today.json")
    if os.path.exists(news_path):
        try:
            with open(news_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            for a in data.get("articles", []):
                news_titles.append(a.get("title", ""))
        except Exception:
            pass

    send_notification(practice_title, news_titles)


if __name__ == "__main__":
    main()
