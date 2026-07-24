#!/usr/bin/env python3
"""
Send a Feishu (Lark) group bot webhook notification with signature verification.

Environment variables:
  FEISHU_WEBHOOK_URL  - Feishu bot webhook URL (required)
  FEISHU_SECRET       - Feishu bot signing secret (required)
  SITE_URL            - The base URL of the GitHub Pages site (required)
"""

import os
import sys
import json
import time
import hashlib
import hmac
import base64
import requests
from datetime import datetime, timezone, timedelta

BJ_TZ = timezone(timedelta(hours=8))

WEBHOOK_URL = os.environ.get("FEISHU_WEBHOOK_URL", "")
SECRET = os.environ.get("FEISHU_SECRET", "")
SITE_URL = os.environ.get("SITE_URL", "").rstrip("/")


def gen_sign(timestamp, secret):
    string_to_sign = "{}\n{}".format(timestamp, secret)
    hmac_code = hmac.new(string_to_sign.encode("utf-8"), digestmod=hashlib.sha256).digest()
    return base64.b64encode(hmac_code).decode("utf-8")


def send_card(card):
    if not WEBHOOK_URL:
        print("FEISHU_WEBHOOK_URL not set, skipping notification.")
        return False
    if not SITE_URL:
        print("SITE_URL not set, skipping notification.")
        return False

    payload = {"msg_type": "interactive", "card": card}

    # Add signature if secret is configured
    if SECRET:
        timestamp = str(int(time.time()))
        sign = gen_sign(timestamp, SECRET)
        payload["timestamp"] = timestamp
        payload["sign"] = sign

    try:
        resp = requests.post(
            WEBHOOK_URL,
            headers={"Content-Type": "application/json"},
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
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


def send_notification(practice_title=None, practice_day=None, news_titles=None):
    """Send a combined Feishu bot card message with today's update info."""
    now = datetime.now(BJ_TZ)
    date_str = now.strftime("%Y-%m-%d")
    date_display = now.strftime("%m月%d日")

    elements = []

    summary_parts = [f"📅 **{date_display}**"]
    if practice_day:
        summary_parts.append(f"Day {practice_day}")
    elements.append({
        "tag": "div",
        "text": {"tag": "lark_md", "content": "  |  ".join(summary_parts)}
    })

    if practice_title:
        elements.append({
            "tag": "div",
            "text": {"tag": "lark_md", "content": f"📖 **口语练习：{practice_title}**"}
        })
        elements.append({
            "tag": "action",
            "actions": [{
                "tag": "button",
                "text": {"tag": "plain_text", "content": "🎧 开始朗读练习"},
                "url": f"{SITE_URL}/english-practice-{date_str}.html",
                "type": "primary"
            }]
        })

    if news_titles:
        news_lines = "\n".join(f"• {t}" for t in news_titles)
        elements.append({
            "tag": "div",
            "text": {"tag": "lark_md", "content": f"📰 **今日新闻：**\n{news_lines}"}
        })
        elements.append({
            "tag": "action",
            "actions": [{
                "tag": "button",
                "text": {"tag": "plain_text", "content": "📻 收听英语新闻"},
                "url": f"{SITE_URL}/english-news-{date_str}.html",
                "type": "danger"
            }]
        })

    elements.append({
        "tag": "action",
        "actions": [{
            "tag": "button",
            "text": {"tag": "plain_text", "content": "🏠 查看全部目录"},
            "url": f"{SITE_URL}/",
            "type": "default"
        }]
    })

    elements.append({
        "tag": "note",
        "elements": [{
            "tag": "plain_text",
            "content": "🔊 全部附带微软神经网络语音朗读 | 每天更新"
        }]
    })

    card = {
        "header": {
            "title": {"tag": "plain_text", "content": "Daily English Practice 已更新"},
            "template": "blue"
        },
        "elements": elements
    }

    return send_card(card)


def main():
    script_dir = os.path.dirname(os.path.abspath(__file__))

    practice_title = None
    practice_day = None
    practice_path = os.path.join(script_dir, "article-today.json")
    if os.path.exists(practice_path):
        try:
            with open(practice_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            practice_title = data.get("title", "")
            practice_day = data.get("day", None)
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

    send_notification(practice_title, practice_day, news_titles)


if __name__ == "__main__":
    main()
