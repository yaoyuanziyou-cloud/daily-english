#!/usr/bin/env python3
"""
Daily orchestrator: generates content, audio, HTML, and sends notification.

Steps:
1. generate_content.py  -> article-today.json + news-today.json
2. generate_practice.py -> english-practice-YYYY-MM-DD.html + audio/
3. generate_news.py     -> english-news-YYYY-MM-DD.html + audio/
4. notify_feishu.py     -> send Feishu webhook notification
5. Cleanup temp JSON files

Usage:
  python run_daily.py
"""

import os
import sys
import subprocess
import json
from datetime import datetime, timezone, timedelta

BJ_TZ = timezone(timedelta(hours=8))
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))


def run_script(script_name, args=None):
    """Run a Python script and return its exit code."""
    cmd = [sys.executable, os.path.join(SCRIPT_DIR, script_name)]
    if args:
        cmd.extend(args)
    print(f"\n{'='*60}")
    print(f"Running: {script_name} {' '.join(args) if args else ''}")
    print(f"{'='*60}")
    result = subprocess.run(cmd, cwd=SCRIPT_DIR)
    return result.returncode


def main():
    now = datetime.now(BJ_TZ)
    date_str = now.strftime("%Y-%m-%d")
    print(f"Daily English Practice Generator")
    print(f"Date: {date_str} (Beijing Time)")
    print(f"Script directory: {SCRIPT_DIR}")

    # Step 1: Generate content JSON via MiniMax API
    rc = run_script("generate_content.py")
    if rc != 0:
        print("WARNING: Content generation had issues, continuing with what we have...")

    # Step 2: Generate practice HTML + audio
    article_json = os.path.join(SCRIPT_DIR, "article-today.json")
    if os.path.exists(article_json):
        rc = run_script("generate_practice.py", ["article-today.json"])
        if rc != 0:
            print("WARNING: Practice HTML generation failed")
    else:
        print("WARNING: article-today.json not found, skipping practice HTML")

    # Step 3: Generate news HTML + audio
    news_json = os.path.join(SCRIPT_DIR, "news-today.json")
    if os.path.exists(news_json):
        rc = run_script("generate_news.py", ["news-today.json"])
        if rc != 0:
            print("WARNING: News HTML generation failed")
    else:
        print("WARNING: news-today.json not found, skipping news HTML")

    # Step 4: Send Feishu notification
    rc = run_script("notify_feishu.py")
    if rc != 0:
        print("WARNING: Feishu notification failed")

    # Step 5: Cleanup temp files
    for temp_file in ["article-today.json", "news-today.json"]:
        temp_path = os.path.join(SCRIPT_DIR, temp_file)
        if os.path.exists(temp_path):
            os.remove(temp_path)
            print(f"Cleaned up: {temp_file}")

    print(f"\n{'='*60}")
    print("Daily generation complete!")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
