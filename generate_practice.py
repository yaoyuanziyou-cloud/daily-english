#!/usr/bin/env python3
"""
Reusable script: Generate an English practice HTML page with neural TTS audio.

Usage:
  python generate_practice.py article.json

article.json format:
{
  "date": "2026-07-25",
  "day": 2,
  "title": "A Weekend Morning at the Cafe",
  "scenario": "Daily Life",
  "sentences": ["Sentence 1.", "Sentence 2.", ...],
  "paragraphs": [[0,1,2], [3,4,5], ...],  // optional: sentence index groups
  "vocab": [["word", "/phonetic/", "中文释义"], ...],
  "phrases": [["phrase", "中文释义和使用场景"], ...],
  "tips": [["标签", "内容"], ...],
  "challenge": "Challenge question text"
}

Output:
  - english-practice-YYYY-MM-DD.html (main page)
  - audio/YYYY-MM-DD/sentence-XX.mp3, word-XX.mp3, phrase-XX.mp3 (audio files)
  - audio/YYYY-MM-DD/full-article.mp3 (combined audio for continuous playback)
"""

import edge_tts
import asyncio
import json
import sys
import os
import html as html_module
from datetime import datetime
from mutagen.mp3 import MP3

VOICE = "en-US-AriaNeural"
REGISTRY_FILE = "articles-registry.json"


async def save_clip(text, filepath, voice=VOICE):
    """Generate a single audio clip and save to file."""
    comm = edge_tts.Communicate(text, voice)
    audio = b""
    async for chunk in comm.stream():
        if chunk["type"] == "audio":
            audio += chunk["data"]
    with open(filepath, "wb") as f:
        f.write(audio)
    return len(audio)


async def generate_all_audio(sentences, vocab_words, phrases, audio_dir):
    """Generate all audio clips and save as files. Returns file lists."""
    result = {"sentences": [], "words": [], "phrases": []}

    print(f"Generating {len(sentences)} sentence clips...")
    for i, s in enumerate(sentences):
        fname = f"sentence-{i:02d}.mp3"
        path = os.path.join(audio_dir, fname)
        size = await save_clip(s, path)
        result["sentences"].append(fname)
        print(f"  [{i+1}/{len(sentences)}] {fname} ({size} bytes)")

    print(f"Generating {len(vocab_words)} vocab clips...")
    for i, w in enumerate(vocab_words):
        fname = f"word-{i:02d}.mp3"
        path = os.path.join(audio_dir, fname)
        size = await save_clip(w, path)
        result["words"].append(fname)
        print(f"  [{i+1}/{len(vocab_words)}] {fname} ({size} bytes)")

    print(f"Generating {len(phrases)} phrase clips...")
    for i, p in enumerate(phrases):
        fname = f"phrase-{i:02d}.mp3"
        path = os.path.join(audio_dir, fname)
        size = await save_clip(p, path)
        result["phrases"].append(fname)
        print(f"  [{i+1}/{len(phrases)}] {fname} ({size} bytes)")

    return result


def build_combined_audio(audio_dir, num_sentences):
    """Concatenate sentence MP3s into one file. Returns (offsets, total_duration)."""
    offsets = []
    combined = bytearray()
    current_offset = 0.0

    for i in range(num_sentences):
        fname = os.path.join(audio_dir, f"sentence-{i:02d}.mp3")
        audio_info = MP3(fname)
        duration = audio_info.info.length
        offsets.append(round(current_offset, 3))
        current_offset += duration
        with open(fname, "rb") as f:
            combined.extend(f.read())

    out_path = os.path.join(audio_dir, "full-article.mp3")
    with open(out_path, "wb") as f:
        f.write(combined)

    total = round(current_offset, 3)
    print(f"Combined audio: {out_path} ({total}s)")
    return offsets, total


def build_html(article, audio_files, audio_rel_dir, sentence_offsets, total_duration):
    """Build the complete HTML page with combined audio for continuous playback."""
    date_str = article["date"]

    word_files_js = json.dumps([f for f in audio_files["words"]])
    phrase_files_js = json.dumps([f for f in audio_files["phrases"]])
    offsets_js = json.dumps(sentence_offsets)

    # Build sentence HTML
    article_html = ""
    first = True
    paras = article.get("paragraphs", None)
    if paras:
        for para in paras:
            article_html += "<p>"
            for s_idx in para:
                text = article["sentences"][s_idx]
                if first:
                    article_html += f'<span class="first-letter">{html_module.escape(text[0])}</span><span class="sentence" data-idx="{s_idx}">{html_module.escape(text[1:])}</span> '
                    first = False
                else:
                    article_html += f'<span class="sentence" data-idx="{s_idx}">{html_module.escape(text)}</span> '
            article_html += "</p>\n"
    else:
        article_html += "<p>"
        for i, s in enumerate(article["sentences"]):
            if first:
                article_html += f'<span class="first-letter">{html_module.escape(s[0])}</span><span class="sentence" data-idx="{i}">{html_module.escape(s[1:])}</span> '
                first = False
            else:
                article_html += f'<span class="sentence" data-idx="{i}">{html_module.escape(s)}</span> '
        article_html += "</p>\n"

    # Build vocab HTML
    vocab_html = ""
    for i, (word, phonetic, meaning) in enumerate(article["vocab"]):
        vocab_html += f'<li><span class="word">{html_module.escape(word)}</span> <span class="phonetic">{html_module.escape(phonetic)}</span> <span class="meaning">{html_module.escape(meaning)}</span> <button class="speak-btn" onclick="playClip(\'word\', {i}, this)" title="Listen">&#128266;</button></li>\n'

    # Build phrases HTML
    phrases_html = ""
    for i, (phrase, desc) in enumerate(article["phrases"]):
        phrases_html += f'<li><div class="phrase-text"><span class="phrase">{html_module.escape(phrase)}</span><div class="desc">{html_module.escape(desc)}</div></div><button class="speak-btn" onclick="playClip(\'phrase\', {i}, this)" title="Listen">&#128266;</button></li>\n'

    # Build tips HTML
    tips_html = ""
    for label, content in article["tips"]:
        tips_html += f'<li><span class="tip-label">{html_module.escape(label)}</span>{html_module.escape(content)}</li>\n'

    # Format date
    try:
        dt = datetime.strptime(date_str, "%Y-%m-%d")
        date_display = dt.strftime("%A, %B %d, %Y")
    except Exception:
        date_display = date_str

    html = f'''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Daily English Practice - {date_str}</title>
<style>
  * {{ margin: 0; padding: 0; box-sizing: border-box; }}
  body {{ font-family: 'Georgia', 'Times New Roman', serif; background: #f5f0e8; color: #2c2c2c; line-height: 1.8; padding: 40px 20px 120px; min-height: 100vh; }}
  .container {{ max-width: 760px; margin: 0 auto; background: #fffdf8; border-radius: 16px; box-shadow: 0 4px 24px rgba(0,0,0,0.08); overflow: hidden; }}
  .player-bar {{ position: sticky; top: 0; z-index: 100; background: linear-gradient(135deg, #1a5276, #2e86c1); color: white; padding: 14px 24px; display: flex; align-items: center; gap: 14px; flex-wrap: wrap; box-shadow: 0 2px 12px rgba(0,0,0,0.15); }}
  .player-bar .play-btn {{ background: white; color: #1a5276; border: none; width: 48px; height: 48px; border-radius: 50%; font-size: 20px; cursor: pointer; display: flex; align-items: center; justify-content: center; transition: all 0.2s; flex-shrink: 0; box-shadow: 0 2px 8px rgba(0,0,0,0.2); }}
  .player-bar .play-btn:hover {{ transform: scale(1.1); }}
  .player-bar .play-btn:active {{ transform: scale(0.95); }}
  .player-bar .stop-btn {{ background: rgba(255,255,255,0.2); color: white; border: 1px solid rgba(255,255,255,0.4); width: 38px; height: 38px; border-radius: 50%; font-size: 14px; cursor: pointer; display: flex; align-items: center; justify-content: center; transition: all 0.2s; flex-shrink: 0; }}
  .player-bar .stop-btn:hover {{ background: rgba(255,255,255,0.35); }}
  .player-bar .speed-control {{ display: flex; align-items: center; gap: 8px; font-family: 'Helvetica', sans-serif; font-size: 13px; }}
  .player-bar .speed-control input[type="range"] {{ width: 90px; cursor: pointer; accent-color: white; }}
  .player-bar .speed-label {{ min-width: 36px; text-align: center; font-variant-numeric: tabular-nums; }}
  .player-bar .repeat-btn {{ background: rgba(255,255,255,0.15); color: white; border: 1px solid rgba(255,255,255,0.3); border-radius: 8px; padding: 7px 14px; font-size: 13px; font-family: 'Helvetica', sans-serif; cursor: pointer; transition: all 0.2s; }}
  .player-bar .repeat-btn:hover {{ background: rgba(255,255,255,0.3); }}
  .player-bar .repeat-btn.active {{ background: #f4d03f; color: #1a5276; border-color: #f4d03f; }}
  .player-bar .voice-badge {{ background: rgba(255,255,255,0.15); border: 1px solid rgba(255,255,255,0.3); border-radius: 8px; padding: 7px 12px; font-size: 12px; font-family: 'Helvetica', sans-serif; display: flex; align-items: center; gap: 6px; }}
  .player-bar .voice-badge .dot {{ width: 8px; height: 8px; border-radius: 50%; background: #4ade80; animation: pulse 1.5s ease-in-out infinite; }}
  @keyframes pulse {{ 0%,100% {{ opacity: 1; }} 50% {{ opacity: 0.4; }} }}
  .player-bar .progress-info {{ font-family: 'Helvetica', sans-serif; font-size: 12px; opacity: 0.8; margin-left: auto; }}
  .player-bar .home-btn {{ background: rgba(255,255,255,0.15); color: white; border: 1px solid rgba(255,255,255,0.3); border-radius: 8px; padding: 7px 14px; font-size: 13px; font-family: 'Helvetica', sans-serif; cursor: pointer; transition: all 0.2s; text-decoration: none; display: flex; align-items: center; gap: 4px; }}
  .player-bar .home-btn:hover {{ background: rgba(255,255,255,0.3); }}
  .progress-bar-container {{ position: relative; width: 100%; height: 6px; background: rgba(255,255,255,0.2); border-radius: 3px; cursor: pointer; margin-top: 4px; }}
  .progress-bar-fill {{ height: 100%; background: #f4d03f; border-radius: 3px; width: 0%; transition: width 0.1s linear; }}
  .header {{ background: linear-gradient(135deg, #1a5276, #2e86c1); color: white; padding: 36px 40px 28px; }}
  .header .date {{ font-size: 13px; letter-spacing: 2px; text-transform: uppercase; opacity: 0.8; margin-bottom: 8px; font-family: 'Helvetica', sans-serif; }}
  .header h1 {{ font-size: 28px; font-weight: normal; line-height: 1.4; }}
  .header .tag {{ display: inline-block; margin-top: 12px; background: rgba(255,255,255,0.2); padding: 4px 14px; border-radius: 20px; font-size: 13px; font-family: 'Helvetica', sans-serif; }}
  .content {{ padding: 36px 40px 40px; }}
  .article {{ font-size: 18px; line-height: 2; margin-bottom: 36px; text-align: justify; }}
  .article p {{ margin-bottom: 16px; }}
  .article .first-letter {{ float: left; font-size: 48px; line-height: 1; margin-right: 8px; margin-top: 4px; color: #2e86c1; font-weight: bold; }}
  .article .sentence {{ cursor: pointer; border-radius: 4px; padding: 0 2px; transition: background 0.2s; }}
  .article .sentence:hover {{ background: #e8f4fc; }}
  .article .sentence.highlighted {{ background: #fceabb; box-shadow: 0 0 0 2px #f4d03f; }}
  .section-title {{ font-family: 'Helvetica', sans-serif; font-size: 16px; font-weight: bold; color: #1a5276; text-transform: uppercase; letter-spacing: 1.5px; margin-bottom: 16px; padding-bottom: 8px; border-bottom: 2px solid #e8e8e8; }}
  .section {{ margin-bottom: 32px; }}
  .vocab-list {{ list-style: none; }}
  .vocab-list li {{ padding: 10px 0; border-bottom: 1px dashed #e0e0e0; font-size: 16px; display: flex; align-items: center; flex-wrap: wrap; }}
  .vocab-list .word {{ font-weight: bold; color: #1a5276; font-size: 17px; }}
  .vocab-list .phonetic {{ color: #888; font-style: italic; font-size: 14px; margin-left: 8px; }}
  .vocab-list .meaning {{ color: #555; margin-left: 8px; flex: 1; }}
  .speak-btn {{ background: #e8f4fc; color: #1a5276; border: none; width: 32px; height: 32px; border-radius: 50%; cursor: pointer; font-size: 15px; display: flex; align-items: center; justify-content: center; transition: all 0.2s; flex-shrink: 0; }}
  .speak-btn:hover {{ background: #2e86c1; color: white; transform: scale(1.15); }}
  .speak-btn.playing {{ background: #f4d03f; color: #1a5276; animation: pulse 1s ease-in-out infinite; }}
  .phrase-list {{ list-style: none; }}
  .phrase-list li {{ padding: 12px 0; border-bottom: 1px dashed #e0e0e0; display: flex; align-items: flex-start; gap: 10px; }}
  .phrase-list .phrase-text {{ flex: 1; }}
  .phrase-list .phrase {{ font-weight: bold; color: #1a5276; font-size: 17px; }}
  .phrase-list .desc {{ color: #666; font-size: 15px; margin-top: 4px; }}
  .phrase-list .speak-btn {{ margin-top: 2px; }}
  .tips-list {{ list-style: none; }}
  .tips-list li {{ padding: 12px 16px; margin-bottom: 10px; background: #f0f6fa; border-left: 4px solid #2e86c1; border-radius: 4px; font-size: 15px; }}
  .tips-list .tip-label {{ font-weight: bold; color: #1a5276; }}
  .challenge {{ background: linear-gradient(135deg, #fef9e7, #fcf3cf); border: 2px solid #f4d03f; border-radius: 12px; padding: 24px; text-align: center; }}
  .challenge .icon {{ font-size: 32px; margin-bottom: 8px; }}
  .challenge .question {{ font-size: 18px; color: #7d6608; font-style: italic; margin-top: 8px; }}
  .footer {{ text-align: center; padding: 20px 40px 32px; color: #aaa; font-size: 13px; font-family: 'Helvetica', sans-serif; }}
</style>
</head>
<body>
<div class="container">
  <div class="player-bar">
    <button class="play-btn" id="playBtn" title="Play / Pause">&#9658;</button>
    <button class="stop-btn" id="stopBtn" title="Stop">&#9632;</button>
    <div class="speed-control">
      <span>Speed</span>
      <input type="range" id="speedSlider" min="0.5" max="1.5" step="0.1" value="0.9">
      <span class="speed-label" id="speedLabel">0.9x</span>
    </div>
    <button class="repeat-btn" id="repeatBtn" title="Loop Mode">&#x21bb; Loop</button>
    <div class="voice-badge"><span class="dot"></span><span>Aria Neural</span></div>
    <span class="progress-info" id="progressInfo">Ready</span>
    <a class="home-btn" href="index.html" title="Back to Index">&#8962; Home</a>
  </div>
  <div style="background: #1a5276; padding: 0 24px 10px;">
    <div class="progress-bar-container" id="progressBarContainer">
      <div class="progress-bar-fill" id="progressBarFill"></div>
    </div>
  </div>

  <div class="header">
    <div class="date">{html_module.escape(date_display)}</div>
    <h1>{html_module.escape(article["title"])}</h1>
    <span class="tag">{html_module.escape(article.get("scenario", ""))}</span>
  </div>

  <div class="content">
    <div class="article" id="articleText">
{article_html}
    </div>

    <div class="section">
      <div class="section-title">Key Vocabulary</div>
      <ul class="vocab-list">
{vocab_html}
      </ul>
    </div>

    <div class="section">
      <div class="section-title">Useful Phrases</div>
      <ul class="phrase-list">
{phrases_html}
      </ul>
    </div>

    <div class="section">
      <div class="section-title">Pronunciation Tips</div>
      <ul class="tips-list">
{tips_html}
      </ul>
    </div>

    <div class="section">
      <div class="section-title">Speaking Challenge</div>
      <div class="challenge">
        <div class="icon">&#127908;&#65039;</div>
        <div class="question">{html_module.escape(article["challenge"])}</div>
      </div>
    </div>
  </div>

  <div class="footer">
    Daily English Speaking Practice &#183; Day {article.get("day", 1)} &#183; Neural TTS by Microsoft Aria &#183; Keep practicing every day!
  </div>
</div>

<audio id="mainAudio" preload="auto">
  <source src="{audio_rel_dir}/full-article.mp3" type="audio/mpeg">
</audio>

<script>
(function() {{
  'use strict';
  var AUDIO_BASE = '{audio_rel_dir}/';
  var SENTENCE_OFFSETS = {offsets_js};
  var WORD_FILES = {word_files_js};
  var PHRASE_FILES = {phrase_files_js};

  var mainAudio = document.getElementById('mainAudio');
  var isPlaying = false;
  var isRepeatMode = false;
  var rate = 0.9;
  var currentSentenceIdx = -1;
  var clipAudio = null;
  var currentButtonEl = null;

  var playBtn = document.getElementById('playBtn');
  var stopBtn = document.getElementById('stopBtn');
  var speedSlider = document.getElementById('speedSlider');
  var speedLabel = document.getElementById('speedLabel');
  var repeatBtn = document.getElementById('repeatBtn');
  var progressInfo = document.getElementById('progressInfo');
  var progressBarFill = document.getElementById('progressBarFill');
  var progressBarContainer = document.getElementById('progressBarContainer');
  var sentenceEls = document.querySelectorAll('.article .sentence');

  mainAudio.playbackRate = rate;

  function highlightSentence(idx) {{
    if (currentSentenceIdx === idx) return;
    currentSentenceIdx = idx;
    sentenceEls.forEach(function(el) {{
      el.classList.toggle('highlighted', parseInt(el.getAttribute('data-idx')) === idx);
    }});
    if (idx >= 0) {{
      var target = document.querySelector('.sentence[data-idx="' + idx + '"]');
      if (target) {{
        var rect = target.getBoundingClientRect();
        if (rect.top < 80 || rect.bottom > window.innerHeight - 40) {{
          target.scrollIntoView({{ behavior: 'smooth', block: 'center' }});
        }}
      }}
    }}
  }}
  function clearHighlights() {{
    currentSentenceIdx = -1;
    sentenceEls.forEach(function(el) {{ el.classList.remove('highlighted'); }});
  }}
  function updateSentenceFromTime() {{
    var t = mainAudio.currentTime;
    for (var i = SENTENCE_OFFSETS.length - 1; i >= 0; i--) {{
      if (t >= SENTENCE_OFFSETS[i]) {{ highlightSentence(i); return; }}
    }}
    highlightSentence(0);
  }}
  function formatTime(sec) {{
    var m = Math.floor(sec / 60);
    var s = Math.floor(sec % 60);
    return m + ':' + (s < 10 ? '0' : '') + s;
  }}

  playBtn.addEventListener('click', function() {{
    if (clipAudio) {{ clipAudio.pause(); clipAudio = null; if (currentButtonEl) {{ currentButtonEl.classList.remove('playing'); currentButtonEl = null; }} }}
    if (mainAudio.paused) {{
      mainAudio.play().then(function() {{
        isPlaying = true;
        playBtn.innerHTML = '&#10074;&#10074;';
      }}).catch(function(e) {{ console.error('Play error:', e); progressInfo.textContent = 'Click again'; }});
    }} else {{
      mainAudio.pause();
      isPlaying = false;
      playBtn.innerHTML = '&#9658;';
      progressInfo.textContent = 'Paused';
    }}
  }});
  stopBtn.addEventListener('click', function() {{
    mainAudio.pause(); mainAudio.currentTime = 0;
    isPlaying = false; clearHighlights();
    playBtn.innerHTML = '&#9658;';
    progressBarFill.style.width = '0%';
    progressInfo.textContent = 'Ready';
  }});
  speedSlider.addEventListener('input', function() {{
    rate = parseFloat(speedSlider.value);
    speedLabel.textContent = rate.toFixed(1) + 'x';
    mainAudio.playbackRate = rate;
  }});
  repeatBtn.addEventListener('click', function() {{
    isRepeatMode = !isRepeatMode;
    repeatBtn.classList.toggle('active', isRepeatMode);
  }});
  mainAudio.addEventListener('timeupdate', function() {{
    var pct = (mainAudio.currentTime / mainAudio.duration) * 100;
    if (isNaN(pct)) pct = 0;
    progressBarFill.style.width = pct + '%';
    updateSentenceFromTime();
    if (mainAudio.duration) {{
      progressInfo.textContent = formatTime(mainAudio.currentTime) + ' / ' + formatTime(mainAudio.duration);
    }}
  }});
  mainAudio.addEventListener('ended', function() {{
    if (isRepeatMode) {{
      mainAudio.currentTime = 0;
      mainAudio.play().catch(function(){{}});
    }} else {{
      isPlaying = false; clearHighlights();
      playBtn.innerHTML = '&#9658;';
      progressInfo.textContent = 'Done';
    }}
  }});
  sentenceEls.forEach(function(el) {{
    el.addEventListener('click', function() {{
      if (clipAudio) {{ clipAudio.pause(); clipAudio = null; if (currentButtonEl) {{ currentButtonEl.classList.remove('playing'); currentButtonEl = null; }} }}
      var idx = parseInt(el.getAttribute('data-idx'));
      if (idx < SENTENCE_OFFSETS.length) {{
        mainAudio.currentTime = SENTENCE_OFFSETS[idx];
        highlightSentence(idx);
        if (mainAudio.paused) {{
          mainAudio.play().then(function() {{ isPlaying = true; playBtn.innerHTML = '&#10074;&#10074;'; }}).catch(function(e) {{ console.error(e); }});
        }}
      }}
    }});
  }});
  progressBarContainer.addEventListener('click', function(e) {{
    var rect = progressBarContainer.getBoundingClientRect();
    var pct = (e.clientX - rect.left) / rect.width;
    if (mainAudio.duration) {{ mainAudio.currentTime = pct * mainAudio.duration; }}
  }});
  window.playClip = function(type, idx, btnEl) {{
    if (!mainAudio.paused) {{ mainAudio.pause(); isPlaying = false; playBtn.innerHTML = '&#9658;'; }}
    if (clipAudio) {{ clipAudio.pause(); clipAudio.src = ''; }}
    if (currentButtonEl) currentButtonEl.classList.remove('playing');
    currentButtonEl = btnEl; btnEl.classList.add('playing');
    var files = (type === 'word') ? WORD_FILES : PHRASE_FILES;
    clipAudio = new Audio(AUDIO_BASE + files[idx]);
    clipAudio.playbackRate = 0.85;
    clipAudio.onended = function() {{ btnEl.classList.remove('playing'); currentButtonEl = null; progressInfo.textContent = 'Ready'; }};
    clipAudio.onerror = function() {{ btnEl.classList.remove('playing'); currentButtonEl = null; }};
    progressInfo.textContent = 'Playing: ' + (type === 'word' ? 'vocabulary' : 'phrase');
    clipAudio.play().catch(function(e) {{ console.error(e); }});
  }};
  mainAudio.load();
}})();
</script>
</body>
</html>'''

    return html


def update_registry_and_index(script_dir, article):
    """Update the articles registry and regenerate index.html (includes news section if present)."""
    registry_path = os.path.join(script_dir, REGISTRY_FILE)

    # Load existing practice registry
    if os.path.exists(registry_path):
        with open(registry_path, "r", encoding="utf-8") as f:
            registry = json.load(f)
    else:
        registry = []

    date_str = article["date"]
    entry = {
        "date": date_str,
        "day": article.get("day", 1),
        "title": article["title"],
        "scenario": article.get("scenario", ""),
        "file": f"english-practice-{date_str}.html",
    }

    # Remove existing entry for same date, then add
    registry = [e for e in registry if e["date"] != date_str]
    registry.append(entry)
    registry.sort(key=lambda e: e["date"])

    with open(registry_path, "w", encoding="utf-8") as f:
        json.dump(registry, f, ensure_ascii=False, indent=2)

    # Load news registry if it exists
    news_registry_path = os.path.join(script_dir, "news-registry.json")
    if os.path.exists(news_registry_path):
        with open(news_registry_path, "r", encoding="utf-8") as f:
            news_registry = json.load(f)
    else:
        news_registry = []

    # Build news cards
    news_cards_html = ""
    for e in reversed(news_registry):
        try:
            dt = datetime.strptime(e["date"], "%Y-%m-%d")
            date_display = dt.strftime("%b %d, %Y")
        except Exception:
            date_display = e["date"]
        article_titles = " / ".join([a["title"] for a in e.get("articles", [])])
        news_cards_html += f'''    <a class="card news-card" href="{html_module.escape(e["file"])}">
      <div class="card-day">News</div>
      <div class="card-date">{html_module.escape(date_display)}</div>
      <div class="card-title">{html_module.escape(article_titles[:100])}</div>
      <div class="card-tag" style="color: #b83b5e; background: #fdf0f4;">{e.get("article_count", 1)} Articles</div>
    </a>
'''

    # Build practice cards
    cards_html = ""
    for e in reversed(registry):
        try:
            dt = datetime.strptime(e["date"], "%Y-%m-%d")
            date_display = dt.strftime("%b %d, %Y")
            weekday = dt.strftime("%A")
        except Exception:
            date_display = e["date"]
            weekday = ""
        is_business = "Business" in e.get("scenario", "")
        tag_color = "#e74c3c" if is_business else "#27ae60"
        tag_bg = "#fdf0ef" if is_business else "#eafaf1"
        cards_html += f'''    <a class="card" href="{html_module.escape(e["file"])}">
      <div class="card-day">Day {e["day"]}</div>
      <div class="card-date">{html_module.escape(date_display)}<span class="card-weekday">{html_module.escape(weekday)}</span></div>
      <div class="card-title">{html_module.escape(e["title"])}</div>
      <div class="card-tag" style="color: {tag_color}; background: {tag_bg};">{html_module.escape(e.get("scenario", ""))}</div>
    </a>
'''

    total_days = len(registry)
    total_news = len(news_registry)

    # Pre-compute news section HTML (avoid backslashes in f-string for Python 3.11)
    news_header_html = ""
    news_grid_html = ""
    if news_cards_html:
        news_header_html = '<div class="section-header news"><span class="icon">&#128240;</span><h2>Daily News</h2></div>'
        news_grid_html = '<div class="grid">' + news_cards_html + '  </div>'

    index_html = f'''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Daily English Practice</title>
<style>
  * {{ margin: 0; padding: 0; box-sizing: border-box; }}
  body {{ font-family: 'Helvetica', 'Arial', sans-serif; background: #f5f0e8; color: #2c2c2c; min-height: 100vh; padding: 40px 20px; }}
  .hero {{ max-width: 800px; margin: 0 auto 36px; text-align: center; }}
  .hero h1 {{ font-family: 'Georgia', serif; font-size: 36px; color: #1a5276; margin-bottom: 10px; }}
  .hero p {{ font-size: 16px; color: #666; line-height: 1.6; }}
  .hero .stats {{ display: flex; justify-content: center; gap: 32px; margin-top: 24px; }}
  .hero .stat {{ text-align: center; }}
  .hero .stat-num {{ font-size: 32px; font-weight: bold; color: #2e86c1; }}
  .hero .stat-label {{ font-size: 13px; color: #999; text-transform: uppercase; letter-spacing: 1px; }}
  .section-header {{ max-width: 800px; margin: 0 auto 16px; display: flex; align-items: center; gap: 10px; }}
  .section-header h2 {{ font-family: 'Georgia', serif; font-size: 22px; color: #1a5276; }}
  .section-header .icon {{ font-size: 24px; }}
  .section-header.news h2 {{ color: #b83b5e; }}
  .grid {{ max-width: 800px; margin: 0 auto 40px; display: grid; grid-template-columns: repeat(auto-fill, minmax(340px, 1fr)); gap: 20px; }}
  .card {{ background: #fffdf8; border-radius: 14px; padding: 24px; text-decoration: none; color: inherit; box-shadow: 0 2px 12px rgba(0,0,0,0.06); transition: all 0.25s; border: 2px solid transparent; display: block; }}
  .card:hover {{ transform: translateY(-4px); box-shadow: 0 8px 28px rgba(0,0,0,0.12); border-color: #2e86c1; }}
  .news-card:hover {{ border-color: #b83b5e; }}
  .news-card {{ background: #fff8fb; }}
  .card-day {{ font-size: 13px; font-weight: bold; color: #2e86c1; text-transform: uppercase; letter-spacing: 1.5px; margin-bottom: 6px; }}
  .news-card .card-day {{ color: #b83b5e; }}
  .card-date {{ font-size: 14px; color: #888; margin-bottom: 12px; }}
  .card-weekday {{ margin-left: 8px; color: #aaa; }}
  .card-title {{ font-family: 'Georgia', serif; font-size: 20px; color: #1a5276; line-height: 1.4; margin-bottom: 14px; }}
  .news-card .card-title {{ color: #6a2c70; font-size: 17px; }}
  .card-tag {{ display: inline-block; padding: 4px 12px; border-radius: 20px; font-size: 12px; font-weight: 600; }}
  .empty {{ text-align: center; padding: 60px 20px; color: #aaa; }}
  .footer {{ text-align: center; padding: 40px 20px; color: #aaa; font-size: 13px; }}
</style>
</head>
<body>
  <div class="hero">
    <h1>Daily English Practice</h1>
    <p>Read aloud every day to build your fluency and natural sense of the language.<br>News articles help you stay informed while improving your English.</p>
    <div class="stats">
      <div class="stat"><div class="stat-num">{total_days}</div><div class="stat-label">Practice Days</div></div>
      <div class="stat"><div class="stat-num">{total_news}</div><div class="stat-label">News Days</div></div>
      <div class="stat"><div class="stat-num">&#127881;</div><div class="stat-label">Keep Going</div></div>
    </div>
  </div>
  {news_header_html}
  {news_grid_html}
  <div class="section-header"><span class="icon">&#128221;</span><h2>Speaking Practice</h2></div>
  <div class="grid">
{cards_html}  </div>
  <div class="footer">Neural TTS by Microsoft Aria &middot; Practice makes perfect</div>
</body>
</html>'''

    index_path = os.path.join(script_dir, "index.html")
    with open(index_path, "w", encoding="utf-8") as f:
        f.write(index_html)

    print(f"Index updated: {index_path} ({total_days} practice, {total_news} news)")
    return index_path


async def main():
    if len(sys.argv) < 2:
        print("Usage: python generate_practice.py article.json")
        sys.exit(1)

    json_path = sys.argv[1]
    script_dir = os.path.dirname(os.path.abspath(json_path))

    with open(json_path, "r", encoding="utf-8") as f:
        article = json.load(f)

    date_str = article["date"]
    vocab_words = [v[0] for v in article["vocab"]]
    phrase_texts = [p[0] for p in article["phrases"]]

    print(f"Article: {article['title']}")
    print(f"Date: {date_str}")
    print(f"Sentences: {len(article['sentences'])}, Vocab: {len(vocab_words)}, Phrases: {len(phrase_texts)}")
    print()

    # Create audio directory
    audio_dir = os.path.join(script_dir, "audio", date_str)
    os.makedirs(audio_dir, exist_ok=True)

    # Generate audio files
    audio_files = await generate_all_audio(article["sentences"], vocab_words, phrase_texts, audio_dir)

    # Build combined audio for continuous playback
    num_sentences = len(article["sentences"])
    sentence_offsets, total_duration = build_combined_audio(audio_dir, num_sentences)

    # Build HTML
    audio_rel_dir = f"audio/{date_str}"
    html = build_html(article, audio_files, audio_rel_dir, sentence_offsets, total_duration)

    output_path = os.path.join(script_dir, f"english-practice-{date_str}.html")
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html)

    print(f"\nHTML written to: {output_path}")
    print(f"Audio files in: {audio_dir}")
    print(f"Total audio files: {len(audio_files['sentences']) + len(audio_files['words']) + len(audio_files['phrases']) + 1} (incl. full-article.mp3)")
    print(f"Total duration: {total_duration}s")

    # Update registry and index page
    update_registry_and_index(script_dir, article)


if __name__ == "__main__":
    asyncio.run(main())
