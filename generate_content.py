#!/usr/bin/env python3
"""
Generate daily English practice article and news content using LLM API.

Supports any OpenAI-compatible API (MiniMax, Groq, Google Gemini, OpenAI, etc.)

Environment variables:
  LLM_API_KEY   - API key (required). Falls back to MINIMAX_API_KEY
  LLM_BASE_URL  - API base URL (default: https://api.minimaxi.com/v1)
  LLM_MODEL     - Model name (default: MiniMax-M3)
"""

import os
import sys
import json
import re
import requests
from datetime import datetime, timezone, timedelta
from openai import OpenAI

# Configuration - supports any OpenAI-compatible API
API_KEY = os.environ.get("LLM_API_KEY", "") or os.environ.get("MINIMAX_API_KEY", "")
BASE_URL = os.environ.get("LLM_BASE_URL", "") or os.environ.get("MINIMAX_BASE_URL", "https://api.minimaxi.com/v1")
MODEL = os.environ.get("LLM_MODEL", "") or os.environ.get("MINIMAX_MODEL", "MiniMax-M3")

# Beijing time
BJ_TZ = timezone(timedelta(hours=8))


def get_client():
    if not API_KEY:
        print("ERROR: MINIMAX_API_KEY environment variable is not set.")
        sys.exit(1)
    return OpenAI(api_key=API_KEY, base_url=BASE_URL)


def llm_chat(client, system_prompt, user_prompt, temperature=0.8, retries=2):
    """Call LLM API and return the text response. Retries on failure."""
    for attempt in range(retries):
        try:
            resp = client.chat.completions.create(
                model=MODEL,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=temperature,
                max_tokens=4096,
            )
            return resp.choices[0].message.content.strip()
        except Exception as e:
            print(f"LLM API error (attempt {attempt+1}/{retries}): {e}")
            if attempt < retries - 1:
                import time
                time.sleep(2)
    return ""


def extract_json(text):
    """Extract JSON object from LLM response (may be wrapped in markdown code blocks)."""
    # Try to find JSON in code blocks
    match = re.search(r'```(?:json)?\s*\n?(.*?)\n?```', text, re.DOTALL)
    if match:
        text = match.group(1)
    # Try direct JSON parse
    text = text.strip()
    # Find the first { and last }
    start = text.find('{')
    end = text.rfind('}')
    if start != -1 and end != -1:
        text = text[start:end+1]
    # Try parsing, with common fixes if it fails
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        # Fix trailing commas
        fixed = re.sub(r',\s*}', '}', text)
        fixed = re.sub(r',\s*]', ']', fixed)
        return json.loads(fixed)


def get_day_number(script_dir):
    """Read the existing registry to determine the next day number."""
    registry_path = os.path.join(script_dir, "articles-registry.json")
    if os.path.exists(registry_path):
        try:
            with open(registry_path, "r", encoding="utf-8") as f:
                registry = json.load(f)
            if registry:
                return max(e.get("day", 0) for e in registry) + 1
        except Exception:
            pass
    return 1


def generate_practice_article(client, script_dir):
    """Generate a daily practice article JSON using MiniMax API."""
    now = datetime.now(BJ_TZ)
    date_str = now.strftime("%Y-%m-%d")
    day = get_day_number(script_dir)

    # Odd days = daily life, even days = business
    if day % 2 == 1:
        scenario_type = "Daily Life"
        topics = [
            "shopping at a supermarket", "ordering food at a restaurant",
            "booking a hotel room", "asking for directions in a new city",
            "planning a weekend trip", "cooking a special meal",
            "visiting a doctor", "taking public transportation",
            "meeting new neighbors", "organizing a home party",
            "going to the gym", "dealing with a lost phone",
            "renting an apartment", "a morning routine",
            "traveling by plane with kids", "gardening on a balcony",
            "a day at the beach", "preparing for a job interview casually",
        ]
    else:
        scenario_type = "Business Scenario"
        topics = [
            "leading a weekly team meeting", "writing a professional email",
            "negotiating a contract", "giving a project presentation",
            "handling a customer complaint", "onboarding a new employee",
            "a salary negotiation", "conducting a performance review",
            "planning a product launch", "resolving a team conflict",
            "a business lunch with a client", "preparing a quarterly report",
            "a video conference with overseas partners", "managing a tight deadline",
            "pitching a new idea to investors", "handling a crisis communication",
        ]

    # Pick topic based on day to ensure variety
    topic = topics[(day - 1) % len(topics)]

    system_prompt = """You are an expert English language teacher creating content for Chinese learners at CEFR B1-B2 level. You generate engaging, natural English content suitable for reading aloud practice. Always respond with valid JSON only."""

    user_prompt = f"""Create a daily English practice article. Requirements:

1. Topic: "{topic}" ({scenario_type})
2. Title: A catchy English title (5-10 words)
3. Sentences: 12-16 sentences, each 8-20 words. Total 200-300 words. Natural, conversational English.
4. Paragraphs: Group sentence indices into paragraphs (2-3 paragraphs).
5. Translations: Provide an accurate Chinese translation for EACH sentence (same count as sentences).
6. Vocabulary: 6-8 key words from the article with phonetic transcription (/.../) and Chinese meaning.
7. Phrases: 4-5 useful phrases with Chinese meaning and usage context.
8. Tips: 2-3 pronunciation tips (linking, weak forms, stress patterns, intonation).
9. Challenge: 1 speaking challenge question using phrases from the article.

Return ONLY a JSON object in this exact format:
{{
  "date": "{date_str}",
  "day": {day},
  "title": "Title Here",
  "scenario": "{scenario_type}",
  "sentences": ["Sentence 1.", "Sentence 2.", ...],
  "paragraphs": [[0,1,2], [3,4,5,6], ...],
  "translations": ["第一句的中文翻译", "第二句的中文翻译", ...],
  "vocab": [["word", "/phonetic/", "Chinese meaning"], ...],
  "phrases": [["phrase", "Chinese meaning and usage context"], ...],
  "tips": [["Linking: ", "Explanation of linking pattern"], ...],
  "challenge": "Challenge question?"
}}

Make the content interesting and practical. Do NOT include any text outside the JSON."""

    print(f"Generating practice article: Day {day}, Topic: {topic}")
    response = llm_chat(client, system_prompt, user_prompt, temperature=0.85)

    if not response:
        print("ERROR: Failed to generate practice article")
        return None

    try:
        article = extract_json(response)
        article["date"] = date_str
        article["day"] = day
        article["scenario"] = scenario_type
        print(f"  Title: {article.get('title', 'N/A')}")
        print(f"  Sentences: {len(article.get('sentences', []))}")
        return article
    except json.JSONDecodeError as e:
        print(f"ERROR: Failed to parse JSON: {e}")
        print(f"Response: {response[:500]}")
        return None


def scrape_china_daily_headlines():
    """Scrape China Daily for latest news headlines and URLs."""
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
    }

    results = []
    urls_to_try = [
        "https://www.chinadaily.com.cn/world",
        "https://www.chinadaily.com.cn/business",
        "https://www.chinadaily.com.cn/china",
        "https://www.chinadaily.com.cn/",
    ]

    # Pattern matches /a/YYYYMM/DD/WS<hex>.html (case-insensitive for hex)
    link_pattern = re.compile(r'href="(/a/\d{6}/\d{2}/WS[a-fA-F0-9]+\.html)"', re.IGNORECASE)

    for url in urls_to_try:
        try:
            resp = requests.get(url, headers=headers, timeout=20)
            resp.encoding = "utf-8"
            links = link_pattern.findall(resp.text)
            for link in links:
                full_url = "https://www.chinadaily.com.cn" + link
                if full_url not in results:
                    results.append(full_url)
            print(f"  {url}: found {len(links)} links")
        except Exception as e:
            print(f"  Warning: Failed to scrape {url}: {e}")

    return results[:15]  # Return top 15 candidates


def scrape_article_content(url):
    """Scrape the full article text from a China Daily URL."""
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }

    try:
        resp = requests.get(url, headers=headers, timeout=15)
        resp.encoding = "utf-8"

        # Extract title
        title_match = re.search(r'<title>(.*?)</title>', resp.text, re.DOTALL)
        title = title_match.group(1).strip() if title_match else ""
        # Clean title - remove site suffix
        title = re.sub(r'\s*[-|]\s*Chinadaily.*$', '', title, flags=re.IGNORECASE).strip()

        # Extract article body text
        # China Daily uses <p> tags within article content area
        p_texts = re.findall(r'<p[^>]*>(.*?)</p>', resp.text, re.DOTALL)
        paragraphs = []
        for p in p_texts:
            # Remove HTML tags
            clean = re.sub(r'<[^>]+>', '', p).strip()
            # Filter out short/irrelevant content
            if len(clean) > 30 and not clean.startswith('Copyright') and not clean.startswith('About Us'):
                paragraphs.append(clean)

        # Take first 6-8 paragraphs as the article body
        body = " ".join(paragraphs[:8])

        return {"title": title, "body": body, "url": url}
    except Exception as e:
        print(f"  Warning: Failed to scrape article {url}: {e}")
        return None


def generate_news_article(client, raw_article):
    """Use MiniMax API to simplify and translate a news article."""
    if not raw_article or not raw_article.get("body"):
        return None

    title = raw_article["title"]
    body = raw_article["body"][:3000]  # Limit input length
    url = raw_article["url"]

    system_prompt = """You are an expert English news editor and translator for Chinese learners. You simplify news articles to CEFR B1-B2 level and provide accurate Chinese translations. Always respond with valid JSON only."""

    user_prompt = f"""Process this news article for English learners.

Original title: {title}
Original content: {body}

Tasks:
1. Create a simplified version with 8-12 sentences (150-200 words total), keeping core information.
2. Each sentence should be 8-20 words, natural and clear.
3. Group sentences into 2-3 paragraphs.
4. Provide accurate Chinese translation for EACH sentence.
5. Select 5-6 key vocabulary words with phonetic transcription and Chinese meaning.
6. Determine the category: Technology, Business, World, Culture, or Sports.

Return ONLY a JSON object:
{{
  "title": "Simplified English Title (keep it close to original)",
  "source": "China Daily",
  "source_url": "{url}",
  "category": "Technology/Business/World/Culture/Sports",
  "sentences": ["Sentence 1.", "Sentence 2.", ...],
  "paragraphs": [[0,1,2], [3,4,5], ...],
  "translations": ["Chinese translation 1", "Chinese translation 2", ...],
  "vocab": [["word", "/phonetic/", "Chinese meaning"], ...]
}}

Do NOT include any text outside the JSON."""

    response = llm_chat(client, system_prompt, user_prompt, temperature=0.3)

    if not response:
        return None

    try:
        article = extract_json(response)
        article["source"] = "China Daily"
        article["source_url"] = url
        print(f"  News: {article.get('title', 'N/A')} [{article.get('category', 'N/A')}]")
        return article
    except json.JSONDecodeError as e:
        print(f"  Warning: Failed to parse news JSON: {e}")
        return None


def generate_news_fallback(client):
    """If China Daily scraping fails, generate news-like content using LLM."""
    now = datetime.now(BJ_TZ)
    date_str = now.strftime("%Y-%m-%d")

    system_prompt = """You are an expert English news editor creating practice content for Chinese learners. Create realistic, educational news content. Always respond with valid JSON only."""

    user_prompt = f"""Create 2 short English news articles for language learning practice. Topics should cover current global trends (technology, economy, culture, environment, etc.). Each article should feel like real news but be simplified for B1-B2 learners.

Return ONLY a JSON object:
{{
  "date": "{date_str}",
  "articles": [
    {{
      "title": "Article 1 Title",
      "source": "China Daily (simulated)",
      "source_url": "",
      "category": "Technology",
      "sentences": ["Sentence 1.", ...],
      "paragraphs": [[0,1,2], [3,4,5]],
      "translations": ["Chinese translation 1", ...],
      "vocab": [["word", "/phonetic/", "Chinese meaning"], ...]
    }},
    {{
      "title": "Article 2 Title",
      "source": "China Daily (simulated)",
      "source_url": "",
      "category": "World",
      "sentences": [...],
      "paragraphs": [...],
      "translations": [...],
      "vocab": [...]
    }}
  ]
}}

Each article: 8-10 sentences, 150-200 words. Include Chinese translations for all sentences. 5-6 vocab words per article."""

    print("Generating fallback news content via LLM...")

    # Try up to 3 times to get valid JSON
    for attempt in range(3):
        response = llm_chat(client, system_prompt, user_prompt, temperature=0.8 if attempt == 0 else 0.5)
        if not response:
            continue
        try:
            return extract_json(response)
        except json.JSONDecodeError as e:
            print(f"  Attempt {attempt+1}: Failed to parse news JSON: {e}")
            if attempt < 2:
                print("  Retrying with lower temperature...")

    print("ERROR: Failed to generate news after 3 attempts")
    return None


def generate_news(client):
    """Generate daily news content: scrape China Daily + LLM processing."""
    now = datetime.now(BJ_TZ)
    date_str = now.strftime("%Y-%m-%d")

    print("\n--- Generating News ---")
    print("Scraping China Daily headlines...")
    article_urls = scrape_china_daily_headlines()
    print(f"  Found {len(article_urls)} candidate articles")

    news_articles = []
    scraped = 0
    for url in article_urls:
        if scraped >= 4:  # Scrape a few extra, we'll pick the best 2
            break
        print(f"  Scraping: {url}")
        raw = scrape_article_content(url)
        if raw and raw.get("body") and len(raw["body"]) > 100:
            processed = generate_news_article(client, raw)
            if processed:
                news_articles.append(processed)
                scraped += 1

    # If we got at least 2, use them
    if len(news_articles) >= 2:
        news_articles = news_articles[:2]
    elif len(news_articles) == 1:
        # Try to get one more
        for url in article_urls[scraped:]:
            raw = scrape_article_content(url)
            if raw and raw.get("body") and len(raw["body"]) > 100:
                processed = generate_news_article(client, raw)
                if processed:
                    news_articles.append(processed)
                    break
        if len(news_articles) < 2:
            # Use fallback for the second article
            print("  Using LLM to generate additional news article...")
            fallback = generate_news_fallback(client)
            if fallback and fallback.get("articles"):
                news_articles.append(fallback["articles"][0])
    else:
        # Scraping failed entirely, use full fallback
        print("  China Daily scraping failed, using LLM fallback...")
        fallback = generate_news_fallback(client)
        if fallback and fallback.get("articles"):
            news_articles = fallback["articles"][:2]

    if not news_articles:
        print("ERROR: Failed to generate any news articles")
        return None

    return {
        "date": date_str,
        "articles": news_articles,
    }


def main():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    client = get_client()

    # Generate practice article
    print("=== Generating Practice Article ===")
    article = generate_practice_article(client, script_dir)
    if article:
        article_path = os.path.join(script_dir, "article-today.json")
        with open(article_path, "w", encoding="utf-8") as f:
            json.dump(article, f, ensure_ascii=False, indent=2)
        print(f"  Saved: article-today.json")
    else:
        print("FAILED to generate practice article")

    # Generate news
    news = generate_news(client)
    if news:
        news_path = os.path.join(script_dir, "news-today.json")
        with open(news_path, "w", encoding="utf-8") as f:
            json.dump(news, f, ensure_ascii=False, indent=2)
        print(f"  Saved: news-today.json")
    else:
        print("FAILED to generate news")

    print("\n=== Content generation complete ===")


if __name__ == "__main__":
    main()
