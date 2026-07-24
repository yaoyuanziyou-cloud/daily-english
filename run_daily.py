#!/usr/bin/env python3
"""
Daily orchestrator: generates content, audio, HTML, and sends notification.

Steps:
1. generate_content.py  -> article-today.json + news-today.json
2. generate_practice.py -> english-practice-YYYY-MM-DD.html + audio/
3. generate_news.py     -> english-news-YYYY-MM-DD.html + audio/
4. notify_feishu.py     -> send Feishu webhook notification
5. Write status.json    -> record run status for index.html display
6. Cleanup temp JSON files

Usage:
  python run_daily.py
"""

import os
import sys
import subprocess
import json
import re
import requests
from datetime import datetime, timezone, timedelta

BJ_TZ = timezone(timedelta(hours=8))
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

# API config (from environment, same as generate_content.py)
API_KEY = os.environ.get("LLM_API_KEY", "") or os.environ.get("MINIMAX_API_KEY", "")
BASE_URL = os.environ.get("LLM_BASE_URL", "") or os.environ.get("MINIMAX_BASE_URL", "https://api.minimaxi.com/v1")
MODEL = os.environ.get("LLM_MODEL", "") or os.environ.get("MINIMAX_MODEL", "MiniMax-M3")


def get_api_provider_name(base_url):
    """Derive a human-readable provider name from the base URL."""
    url_lower = base_url.lower()
    if "jointpilot" in url_lower or "moonshot" in url_lower or "kimi" in url_lower:
        return "Kimi"
    if "minimax" in url_lower:
        return "MiniMax"
    if "openai.com" in url_lower:
        return "OpenAI"
    if "groq" in url_lower:
        return "Groq"
    if "deepseek" in url_lower:
        return "DeepSeek"
    if "anthropic" in url_lower:
        return "Anthropic"
    # Fallback: extract domain
    match = re.search(r"https?://([^/]+)", base_url)
    return match.group(1) if match else "Unknown"


def check_api_balance():
    """Try to fetch API balance/quota from common proxy endpoints."""
    if not API_KEY or not BASE_URL:
        return None

    headers = {"Authorization": f"Bearer {API_KEY}"}
    base = BASE_URL.rstrip("/").rstrip("/v1")

    # Try One API / New API style endpoints
    endpoints_to_try = [
        f"{base}/api/user/self",
        f"{BASE_URL}/dashboard/billing/credit_grants",
        f"{BASE_URL}/dashboard/billing/subscription",
    ]

    for url in endpoints_to_try:
        try:
            resp = requests.get(url, headers=headers, timeout=10)
            if resp.status_code == 200:
                data = resp.json()
                # One API / New API format
                if "data" in data and isinstance(data["data"], dict):
                    d = data["data"]
                    quota = d.get("quota", 0)
                    used = d.get("used_quota", 0)
                    if quota is not None:
                        # Quota is typically in cents or micro-dollars
                        remaining = quota - used
                        # Try to convert to a readable format
                        if remaining > 10000:
                            balance_str = f"${remaining / 500000:.2f}"
                        elif remaining > 100:
                            balance_str = f"${remaining / 500000:.4f}"
                        else:
                            balance_str = f"{remaining} units"
                        return {
                            "balance": balance_str,
                            "quota": quota,
                            "used": used,
                            "remaining": remaining,
                            "source": url
                        }
                # OpenAI style
                if "total_granted" in data:
                    return {
                        "balance": f"${data.get('total_available', 0) / 100:.2f}",
                        "source": url
                    }
        except Exception:
            continue

    return None


def run_script(script_name, args=None):
    """Run a Python script and return its exit code and output."""
    cmd = [sys.executable, os.path.join(SCRIPT_DIR, script_name)]
    if args:
        cmd.extend(args)
    print(f"\n{'='*60}")
    print(f"Running: {script_name} {' '.join(args) if args else ''}")
    print(f"{'='*60}")
    result = subprocess.run(cmd, cwd=SCRIPT_DIR, capture_output=True, text=True)
    # Print the output so it shows in GitHub Actions logs
    if result.stdout:
        print(result.stdout)
    if result.stderr:
        print(result.stderr)
    return result.returncode, result.stdout + result.stderr


def write_status(status, error=None, practice_title=None, news_titles=None, balance=None):
    """Write status.json for index.html to display."""
    now = datetime.now(BJ_TZ)
    provider = get_api_provider_name(BASE_URL)

    status_data = {
        "last_run": now.isoformat(),
        "date": now.strftime("%Y-%m-%d"),
        "time": now.strftime("%H:%M"),
        "status": status,
        "api_provider": provider,
        "model": MODEL,
        "base_url": BASE_URL,
        "balance": balance,
        "error": error,
        "practice_title": practice_title,
        "news_titles": news_titles or [],
    }

    status_path = os.path.join(SCRIPT_DIR, "status.json")
    with open(status_path, "w", encoding="utf-8") as f:
        json.dump(status_data, f, ensure_ascii=False, indent=2)
    print(f"\nStatus written to: {status_path}")
    print(json.dumps(status_data, ensure_ascii=False, indent=2))


def extract_titles_from_output(output):
    """Try to extract practice title and news titles from script output."""
    practice_title = None
    news_titles = []

    for line in output.split("\n"):
        # Look for "Title:" or "title:" patterns
        match = re.search(r"(?:Title|title):\s*(.+)", line)
        if match:
            title = match.group(1).strip()
            if "news" in line.lower() or "article" in line.lower():
                news_titles.append(title)
            elif not practice_title:
                practice_title = title
        # Also look for "Article:" pattern
        match2 = re.search(r"Article \d+:\s*(.+)", line)
        if match2:
            news_titles.append(match2.group(1).strip())
        # Look for "  [0]" or "  [1]" pattern (from generate_content.py)
        match3 = re.search(r"\[\d+\]\s*(.+)", line)
        if match3 and "title" in line.lower():
            news_titles.append(match3.group(1).strip())

    return practice_title, news_titles


def detect_api_error(output):
    """Check if the output contains API-related errors."""
    output_lower = output.lower()
    error_patterns = [
        ("insufficient balance", "API 余额不足，请充值后重试"),
        ("quota exceeded", "API 额度已用尽"),
        ("401", "API Key 认证失败，请检查 Key 是否正确"),
        ("402", "API 余额不足，需要付费"),
        ("403", "API 访问被拒绝"),
        ("429", "API 请求频率过高，请稍后重试"),
        ("invalid authentication", "API Key 无效，请检查配置"),
        ("rate limit", "API 请求频率限制"),
        ("connection", "API 连接失败，请检查网络或 Base URL"),
    ]
    for pattern, message in error_patterns:
        if pattern in output_lower:
            return message
    return None


def main():
    now = datetime.now(BJ_TZ)
    date_str = now.strftime("%Y-%m-%d")
    print(f"Daily English Practice Generator")
    print(f"Date: {date_str} (Beijing Time)")
    print(f"Script directory: {SCRIPT_DIR}")
    print(f"API Provider: {get_api_provider_name(BASE_URL)}")
    print(f"Model: {MODEL}")

    all_output = ""
    has_error = False
    error_message = None
    practice_title = None
    news_titles = []

    # Step 1: Generate content JSON via LLM API
    rc, output = run_script("generate_content.py")
    all_output += output
    if rc != 0:
        print("WARNING: Content generation had issues, continuing with what we have...")
        has_error = True
        error_message = detect_api_error(output)

    # Extract titles from output
    pt, nt = extract_titles_from_output(output)
    if pt:
        practice_title = pt
    if nt:
        news_titles = nt

    # Step 2: Generate practice HTML + audio
    article_json = os.path.join(SCRIPT_DIR, "article-today.json")
    if os.path.exists(article_json):
        # Try to read title from JSON
        try:
            with open(article_json, "r", encoding="utf-8") as f:
                article_data = json.load(f)
            practice_title = article_data.get("title", practice_title)
        except Exception:
            pass
        rc, output = run_script("generate_practice.py", ["article-today.json"])
        all_output += output
        if rc != 0:
            print("WARNING: Practice HTML generation failed")
            has_error = True
            if not error_message:
                error_message = "练习页面生成失败"
    else:
        print("WARNING: article-today.json not found, skipping practice HTML")
        has_error = True
        if not error_message:
            error_message = "内容生成失败（article-today.json 未生成）"

    # Step 3: Generate news HTML + audio
    news_json = os.path.join(SCRIPT_DIR, "news-today.json")
    if os.path.exists(news_json):
        # Try to read titles from JSON
        try:
            with open(news_json, "r", encoding="utf-8") as f:
                news_data = json.load(f)
            news_titles = [a.get("title", "") for a in news_data.get("articles", [])]
        except Exception:
            pass
        rc, output = run_script("generate_news.py", ["news-today.json"])
        all_output += output
        if rc != 0:
            print("WARNING: News HTML generation failed")
            has_error = True
            if not error_message:
                error_message = "新闻页面生成失败"
    else:
        print("WARNING: news-today.json not found, skipping news HTML")

    # Step 4: Send Feishu notification
    rc, output = run_script("notify_feishu.py")
    all_output += output
    if rc != 0:
        print("WARNING: Feishu notification failed")

    # Step 5: Check API balance
    print("\nChecking API balance...")
    balance = check_api_balance()
    if balance:
        print(f"Balance: {balance.get('balance', 'unknown')}")
    else:
        print("Could not retrieve balance info (this is normal for some providers)")

    # Step 6: Write status.json
    if has_error and not practice_title and not news_titles:
        status = "failed"
    elif has_error:
        status = "partial"
    else:
        status = "success"

    write_status(status, error_message, practice_title, news_titles, balance)

    # Step 7: Cleanup temp files
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
