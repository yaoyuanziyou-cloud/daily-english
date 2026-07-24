#!/usr/bin/env python3
"""
Generate a daily English news HTML page with neural TTS audio and Chinese translations.

Usage:
  python generate_news.py news.json

news.json format:
{
  "date": "2026-07-24",
  "articles": [
    {
      "title": "Article Title",
      "source": "China Daily",
      "source_url": "https://...",
      "category": "Technology",
      "sentences": ["Sentence 1.", "Sentence 2.", ...],
      "paragraphs": [[0,1,2], [3,4,5], ...],
      "translations": ["中文翻译1", "中文翻译2", ...],
      "vocab": [["word", "/phonetic/", "中文释义"], ...]
    },
    ...
  ]
}

Output:
  - english-news-YYYY-MM-DD.html
  - audio/news-YYYY-MM-DD/artN-sentence-XX.mp3, artN-word-XX.mp3 (audio files)
  - audio/news-YYYY-MM-DD/artN-full.mp3 (combined audio per article)
  - Updates index.html and news-registry.json
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
NEWS_REGISTRY_FILE = "news-registry.json"
PRACTICE_REGISTRY_FILE = "articles-registry.json"


async def save_clip(text, filepath, voice=VOICE):
    comm = edge_tts.Communicate(text, voice)
    audio = b""
    async for chunk in comm.stream():
        if chunk["type"] == "audio":
            audio += chunk["data"]
    with open(filepath, "wb") as f:
        f.write(audio)
    return len(audio)


async def generate_article_audio(article, audio_dir, art_idx):
    """Generate all audio clips for one article. Returns dict of file lists."""
    result = {"sentences": [], "words": []}
    prefix = f"art{art_idx}"

    sentences = article["sentences"]
    print(f"  Article {art_idx}: Generating {len(sentences)} sentence clips...")
    for i, s in enumerate(sentences):
        fname = f"{prefix}-sentence-{i:02d}.mp3"
        path = os.path.join(audio_dir, fname)
        size = await save_clip(s, path)
        result["sentences"].append(fname)

    vocab_words = [v[0] for v in article.get("vocab", [])]
    print(f"  Article {art_idx}: Generating {len(vocab_words)} vocab clips...")
    for i, w in enumerate(vocab_words):
        fname = f"{prefix}-word-{i:02d}.mp3"
        path = os.path.join(audio_dir, fname)
        size = await save_clip(w, path)
        result["words"].append(fname)

    return result


def build_combined_audio(audio_dir, art_idx, num_sentences):
    """Concatenate sentence MP3s into one file for an article."""
    prefix = f"art{art_idx}"
    offsets = []
    combined = bytearray()
    current_offset = 0.0

    for i in range(num_sentences):
        fname = os.path.join(audio_dir, f"{prefix}-sentence-{i:02d}.mp3")
        audio_info = MP3(fname)
        duration = audio_info.info.length
        offsets.append(round(current_offset, 3))
        current_offset += duration
        with open(fname, "rb") as f:
            combined.extend(f.read())

    out_path = os.path.join(audio_dir, f"{prefix}-full.mp3")
    with open(out_path, "wb") as f:
        f.write(combined)

    total = round(current_offset, 3)
    print(f"  Article {art_idx}: Combined audio ({total}s)")
    return offsets, total, f"{prefix}-full.mp3"


def build_html(data, all_audio, audio_rel_dir):
    """Build the complete news HTML page."""
    date_str = data["date"]
    articles = data["articles"]

    # Build each article section
    articles_html = ""
    articles_js = []

    for art_idx, article in enumerate(articles):
        art_audio = all_audio[art_idx]
        offsets = art_audio["offsets"]
        full_file = art_audio["full_file"]
        word_files = art_audio["words"]

        paras = article.get("paragraphs", None)

        # Build English text with sentence spans
        en_html = ""
        if paras:
            for para in paras:
                en_html += "<p>"
                for s_idx in para:
                    text = article["sentences"][s_idx]
                    en_html += f'<span class="sentence" data-art="{art_idx}" data-idx="{s_idx}">{html_module.escape(text)}</span> '
                en_html += "</p>\n"
        else:
            en_html += "<p>"
            for i, s in enumerate(article["sentences"]):
                en_html += f'<span class="sentence" data-art="{art_idx}" data-idx="{i}">{html_module.escape(s)}</span> '
            en_html += "</p>\n"

        # Build Chinese translation
        cn_html = ""
        if paras:
            for para in paras:
                cn_html += "<p>"
                for s_idx in para:
                    cn_html += f'<span>{html_module.escape(article["translations"][s_idx])}</span> '
                cn_html += "</p>\n"
        else:
            cn_html += "<p>"
            for t in article["translations"]:
                cn_html += f'<span>{html_module.escape(t)}</span> '
            cn_html += "</p>\n"

        # Build vocab
        vocab_html = ""
        for i, (word, phonetic, meaning) in enumerate(article.get("vocab", [])):
            vocab_html += f'<li><span class="word">{html_module.escape(word)}</span> <span class="phonetic">{html_module.escape(phonetic)}</span> <span class="meaning">{html_module.escape(meaning)}</span> <button class="speak-btn" onclick="playWord({art_idx}, {i}, this)" title="Listen">&#128266;</button></li>\n'

        # Category color
        cat = article.get("category", "News")
        cat_colors = {
            "Technology": ("#8e44ad", "#f5eef8"),
            "Business": ("#e74c3c", "#fdf0ef"),
            "World": ("#2980b9", "#ebf5fb"),
            "Culture": ("#e67e22", "#fef5ec"),
            "Sports": ("#27ae60", "#eafaf1"),
        }
        tag_color, tag_bg = cat_colors.get(cat, ("#2c3e50", "#eceff1"))

        vocab_section_html = ""
        if vocab_html.strip():
            vocab_section_html = '<div class="vocab-section"><div class="section-title">Key Vocabulary</div><ul class="vocab-list">' + vocab_html + '</ul></div>'

        articles_html += f'''
    <div class="article-section" id="article-{art_idx}">
      <div class="article-header">
        <h2>{html_module.escape(article["title"])}</h2>
        <div class="article-meta">
          <span class="cat-tag" style="color: {tag_color}; background: {tag_bg};">{html_module.escape(cat)}</span>
          <a href="{html_module.escape(article.get("source_url", "#"))}" target="_blank" class="source-link">Source: {html_module.escape(article.get("source", "China Daily"))} &#8599;</a>
        </div>
      </div>

      <div class="article-player">
        <button class="art-play-btn" id="playBtn-{art_idx}" onclick="toggleArticle({art_idx})" title="Play / Pause">&#9658;</button>
        <div class="art-progress-container" id="progressContainer-{art_idx}" onclick="seekArticle({art_idx}, event)">
          <div class="art-progress-fill" id="progressFill-{art_idx}"></div>
        </div>
        <span class="art-time" id="artTime-{art_idx}">Ready</span>
      </div>

      <div class="article-body">
        <div class="en-text" id="enText-{art_idx}">
{en_html}        </div>
        <button class="translate-toggle" onclick="toggleTranslation({art_idx})" id="transToggle-{art_idx}">&#128257; Show Chinese Translation</button>
        <div class="cn-text" id="cnText-{art_idx}" style="display:none;">
{cn_html}        </div>
      </div>

      {vocab_section_html}
    </div>
'''

        articles_js.append({
            "offsets": offsets,
            "fullFile": f"{audio_rel_dir}/{full_file}",
            "wordFiles": [f"{audio_rel_dir}/{f}" for f in word_files],
        })

    # Format date
    try:
        dt = datetime.strptime(date_str, "%Y-%m-%d")
        date_display = dt.strftime("%A, %B %d, %Y")
    except Exception:
        date_display = date_str

    articles_js_str = json.dumps(articles_js)

    html = f'''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Daily English News - {date_str}</title>
<style>
  * {{ margin: 0; padding: 0; box-sizing: border-box; }}
  body {{ font-family: 'Georgia', 'Times New Roman', serif; background: #f5f0e8; color: #2c2c2c; line-height: 1.8; padding: 40px 20px 120px; min-height: 100vh; }}
  .container {{ max-width: 760px; margin: 0 auto; background: #fffdf8; border-radius: 16px; box-shadow: 0 4px 24px rgba(0,0,0,0.08); overflow: hidden; }}
  .top-bar {{ position: sticky; top: 0; z-index: 100; background: linear-gradient(135deg, #6a2c70, #b83b5e); color: white; padding: 14px 24px; display: flex; align-items: center; gap: 14px; flex-wrap: wrap; box-shadow: 0 2px 12px rgba(0,0,0,0.15); }}
  .top-bar .speed-control {{ display: flex; align-items: center; gap: 8px; font-family: 'Helvetica', sans-serif; font-size: 13px; }}
  .top-bar .speed-control input[type="range"] {{ width: 90px; cursor: pointer; accent-color: white; }}
  .top-bar .speed-label {{ min-width: 36px; text-align: center; font-variant-numeric: tabular-nums; }}
  .top-bar .repeat-btn {{ background: rgba(255,255,255,0.15); color: white; border: 1px solid rgba(255,255,255,0.3); border-radius: 8px; padding: 7px 14px; font-size: 13px; font-family: 'Helvetica', sans-serif; cursor: pointer; transition: all 0.2s; }}
  .top-bar .repeat-btn:hover {{ background: rgba(255,255,255,0.3); }}
  .top-bar .repeat-btn.active {{ background: #f4d03f; color: #6a2c70; border-color: #f4d03f; }}
  .top-bar .voice-badge {{ background: rgba(255,255,255,0.15); border: 1px solid rgba(255,255,255,0.3); border-radius: 8px; padding: 7px 12px; font-size: 12px; font-family: 'Helvetica', sans-serif; display: flex; align-items: center; gap: 6px; }}
  .top-bar .voice-badge .dot {{ width: 8px; height: 8px; border-radius: 50%; background: #4ade80; animation: pulse 1.5s ease-in-out infinite; }}
  @keyframes pulse {{ 0%,100% {{ opacity: 1; }} 50% {{ opacity: 0.4; }} }}
  .top-bar .home-btn {{ background: rgba(255,255,255,0.15); color: white; border: 1px solid rgba(255,255,255,0.3); border-radius: 8px; padding: 7px 14px; font-size: 13px; font-family: 'Helvetica', sans-serif; cursor: pointer; transition: all 0.2s; text-decoration: none; display: flex; align-items: center; gap: 4px; margin-left: auto; }}
  .top-bar .home-btn:hover {{ background: rgba(255,255,255,0.3); }}
  .header {{ background: linear-gradient(135deg, #6a2c70, #b83b5e); color: white; padding: 36px 40px 28px; }}
  .header .date {{ font-size: 13px; letter-spacing: 2px; text-transform: uppercase; opacity: 0.8; margin-bottom: 8px; font-family: 'Helvetica', sans-serif; }}
  .header h1 {{ font-size: 28px; font-weight: normal; line-height: 1.4; }}
  .header .subtitle {{ font-size: 14px; opacity: 0.8; margin-top: 8px; font-family: 'Helvetica', sans-serif; }}
  .content {{ padding: 36px 40px 40px; }}
  .article-section {{ margin-bottom: 48px; padding-bottom: 36px; border-bottom: 1px solid #e8e8e8; }}
  .article-section:last-child {{ border-bottom: none; }}
  .article-header h2 {{ font-size: 22px; color: #2c2c2c; line-height: 1.4; margin-bottom: 12px; }}
  .article-meta {{ display: flex; align-items: center; gap: 12px; flex-wrap: wrap; margin-bottom: 20px; }}
  .cat-tag {{ display: inline-block; padding: 4px 12px; border-radius: 20px; font-size: 12px; font-weight: 600; font-family: 'Helvetica', sans-serif; }}
  .source-link {{ font-size: 13px; color: #b83b5e; text-decoration: none; font-family: 'Helvetica', sans-serif; }}
  .source-link:hover {{ text-decoration: underline; }}
  .article-player {{ display: flex; align-items: center; gap: 12px; margin-bottom: 24px; background: #f8f0f4; border-radius: 10px; padding: 10px 16px; }}
  .art-play-btn {{ background: #b83b5e; color: white; border: none; width: 42px; height: 42px; border-radius: 50%; font-size: 16px; cursor: pointer; display: flex; align-items: center; justify-content: center; transition: all 0.2s; flex-shrink: 0; box-shadow: 0 2px 8px rgba(0,0,0,0.15); }}
  .art-play-btn:hover {{ transform: scale(1.1); background: #6a2c70; }}
  .art-progress-container {{ flex: 1; height: 6px; background: #e8d5dd; border-radius: 3px; cursor: pointer; }}
  .art-progress-fill {{ height: 100%; background: #b83b5e; border-radius: 3px; width: 0%; transition: width 0.1s linear; }}
  .art-time {{ font-family: 'Helvetica', sans-serif; font-size: 12px; color: #888; min-width: 60px; text-align: right; }}
  .article-body .en-text {{ font-size: 17px; line-height: 2; text-align: justify; }}
  .article-body .en-text p {{ margin-bottom: 14px; }}
  .article-body .sentence {{ cursor: pointer; border-radius: 4px; padding: 0 2px; transition: background 0.2s; }}
  .article-body .sentence:hover {{ background: #f3e5ed; }}
  .article-body .sentence.highlighted {{ background: #fceabb; box-shadow: 0 0 0 2px #f4d03f; }}
  .translate-toggle {{ background: #f0e6ed; color: #6a2c70; border: 1px solid #d4a5b8; border-radius: 8px; padding: 8px 16px; font-size: 14px; font-family: 'Helvetica', sans-serif; cursor: pointer; transition: all 0.2s; margin-top: 16px; }}
  .translate-toggle:hover {{ background: #e8d5dd; }}
  .translate-toggle.active {{ background: #6a2c70; color: white; }}
  .cn-text {{ font-size: 16px; line-height: 1.9; color: #555; margin-top: 16px; padding: 16px 20px; background: #f9f5f7; border-left: 4px solid #b83b5e; border-radius: 4px; font-family: 'PingFang SC', 'Microsoft YaHei', 'Helvetica', sans-serif; }}
  .cn-text p {{ margin-bottom: 10px; }}
  .vocab-section {{ margin-top: 24px; }}
  .section-title {{ font-family: 'Helvetica', sans-serif; font-size: 14px; font-weight: bold; color: #6a2c70; text-transform: uppercase; letter-spacing: 1.5px; margin-bottom: 12px; padding-bottom: 6px; border-bottom: 2px solid #f0e6ed; }}
  .vocab-list {{ list-style: none; }}
  .vocab-list li {{ padding: 8px 0; border-bottom: 1px dashed #e0e0e0; font-size: 15px; display: flex; align-items: center; flex-wrap: wrap; }}
  .vocab-list .word {{ font-weight: bold; color: #6a2c70; font-size: 16px; }}
  .vocab-list .phonetic {{ color: #888; font-style: italic; font-size: 13px; margin-left: 8px; }}
  .vocab-list .meaning {{ color: #555; margin-left: 8px; flex: 1; }}
  .speak-btn {{ background: #f3e5ed; color: #6a2c70; border: none; width: 30px; height: 30px; border-radius: 50%; cursor: pointer; font-size: 14px; display: flex; align-items: center; justify-content: center; transition: all 0.2s; flex-shrink: 0; }}
  .speak-btn:hover {{ background: #b83b5e; color: white; transform: scale(1.15); }}
  .speak-btn.playing {{ background: #f4d03f; color: #6a2c70; animation: pulse 1s ease-in-out infinite; }}
  .footer {{ text-align: center; padding: 20px 40px 32px; color: #aaa; font-size: 13px; font-family: 'Helvetica', sans-serif; }}
</style>
</head>
<body>
<div class="container">
  <div class="top-bar">
    <div class="speed-control">
      <span>Speed</span>
      <input type="range" id="speedSlider" min="0.5" max="1.5" step="0.1" value="0.9">
      <span class="speed-label" id="speedLabel">0.9x</span>
    </div>
    <button class="repeat-btn" id="repeatBtn" title="Loop Mode">&#x21bb; Loop</button>
    <div class="voice-badge"><span class="dot"></span><span>Aria Neural</span></div>
    <a class="home-btn" href="index.html" title="Back to Index">&#8962; Home</a>
  </div>

  <div class="header">
    <div class="date">{html_module.escape(date_display)}</div>
    <h1>Daily English News</h1>
    <div class="subtitle">Read along to build your vocabulary and natural sense of the language</div>
  </div>

  <div class="content">
{articles_html}  </div>

  <div class="footer">
    Daily English News &middot; Source: China Daily &middot; Neural TTS by Microsoft Aria
  </div>
</div>

<script>
(function() {{
  'use strict';
  var ARTICLES = {articles_js_str};
  var rate = 0.9;
  var isRepeatMode = false;
  var currentArtIdx = -1;
  var currentSentenceIdx = -1;
  var audios = [];
  var clipAudio = null;
  var currentBtnEl = null;

  // Create audio elements for each article
  for (var i = 0; i < ARTICLES.length; i++) {{
    var a = new Audio(ARTICLES[i].fullFile);
    a.preload = 'auto';
    a.playbackRate = rate;
    (function(idx) {{
      a.addEventListener('timeupdate', function() {{
        updateProgress(idx);
      }});
      a.addEventListener('ended', function() {{
        if (isRepeatMode) {{
          audios[idx].currentTime = 0;
          audios[idx].play().catch(function(){{}});
        }} else {{
          resetArticleUI(idx);
        }}
      }});
    }})(i);
    audios.push(a);
  }}

  var speedSlider = document.getElementById('speedSlider');
  var speedLabel = document.getElementById('speedLabel');
  var repeatBtn = document.getElementById('repeatBtn');

  speedSlider.addEventListener('input', function() {{
    rate = parseFloat(speedSlider.value);
    speedLabel.textContent = rate.toFixed(1) + 'x';
    audios.forEach(function(a) {{ a.playbackRate = rate; }});
  }});

  repeatBtn.addEventListener('click', function() {{
    isRepeatMode = !isRepeatMode;
    repeatBtn.classList.toggle('active', isRepeatMode);
  }});

  function stopAll() {{
    for (var i = 0; i < audios.length; i++) {{
      if (!audios[i].paused) {{
        audios[i].pause();
        resetArticleUI(i);
      }}
    }}
    if (clipAudio) {{
      clipAudio.pause(); clipAudio.src = '';
      if (currentBtnEl) {{ currentBtnEl.classList.remove('playing'); currentBtnEl = null; }}
    }}
  }}

  function resetArticleUI(idx) {{
    var btn = document.getElementById('playBtn-' + idx);
    if (btn) btn.innerHTML = '&#9658;';
    var fill = document.getElementById('progressFill-' + idx);
    if (fill) fill.style.width = '0%';
    var time = document.getElementById('artTime-' + idx);
    if (time) time.textContent = 'Ready';
    clearHighlights(idx);
  }}

  function clearHighlights(artIdx) {{
    var els = document.querySelectorAll('.sentence[data-art="' + artIdx + '"]');
    els.forEach(function(el) {{ el.classList.remove('highlighted'); }});
  }}

  function highlightSentence(artIdx, sentIdx) {{
    clearHighlights(artIdx);
    var el = document.querySelector('.sentence[data-art="' + artIdx + '"][data-idx="' + sentIdx + '"]');
    if (el) {{
      el.classList.add('highlighted');
      var rect = el.getBoundingClientRect();
      if (rect.top < 80 || rect.bottom > window.innerHeight - 40) {{
        el.scrollIntoView({{ behavior: 'smooth', block: 'center' }});
      }}
    }}
  }}

  function updateProgress(idx) {{
    var a = audios[idx];
    var pct = (a.currentTime / a.duration) * 100;
    if (isNaN(pct)) pct = 0;
    var fill = document.getElementById('progressFill-' + idx);
    if (fill) fill.style.width = pct + '%';
    var time = document.getElementById('artTime-' + idx);
    if (time && a.duration) {{
      time.textContent = formatTime(a.currentTime) + ' / ' + formatTime(a.duration);
    }}
    // Update sentence highlight
    var offsets = ARTICLES[idx].offsets;
    for (var i = offsets.length - 1; i >= 0; i--) {{
      if (a.currentTime >= offsets[i]) {{
        if (currentArtIdx !== idx || currentSentenceIdx !== i) {{
          currentArtIdx = idx;
          currentSentenceIdx = i;
          highlightSentence(idx, i);
        }}
        return;
      }}
    }}
  }}

  function formatTime(sec) {{
    var m = Math.floor(sec / 60);
    var s = Math.floor(sec % 60);
    return m + ':' + (s < 10 ? '0' : '') + s;
  }}

  window.toggleArticle = function(idx) {{
    var a = audios[idx];
    if (clipAudio) {{ clipAudio.pause(); clipAudio.src = ''; if (currentBtnEl) {{ currentBtnEl.classList.remove('playing'); currentBtnEl = null; }} }}
    if (a.paused) {{
      // Stop other articles
      for (var i = 0; i < audios.length; i++) {{
        if (i !== idx && !audios[i].paused) {{
          audios[i].pause();
          resetArticleUI(i);
        }}
      }}
      a.play().then(function() {{
        var btn = document.getElementById('playBtn-' + idx);
        if (btn) btn.innerHTML = '&#10074;&#10074;';
        currentArtIdx = idx;
      }}).catch(function(e) {{ console.error('Play error:', e); }});
    }} else {{
      a.pause();
      var btn = document.getElementById('playBtn-' + idx);
      if (btn) btn.innerHTML = '&#9658;';
      var time = document.getElementById('artTime-' + idx);
      if (time) time.textContent = 'Paused';
    }}
  }};

  window.seekArticle = function(idx, e) {{
    var a = audios[idx];
    var container = document.getElementById('progressContainer-' + idx);
    var rect = container.getBoundingClientRect();
    var pct = (e.clientX - rect.left) / rect.width;
    if (a.duration) a.currentTime = pct * a.duration;
  }};

  // Click sentence to jump
  document.querySelectorAll('.sentence').forEach(function(el) {{
    el.addEventListener('click', function() {{
      var artIdx = parseInt(el.getAttribute('data-art'));
      var sentIdx = parseInt(el.getAttribute('data-idx'));
      var a = audios[artIdx];
      var offsets = ARTICLES[artIdx].offsets;
      if (sentIdx < offsets.length) {{
        // Stop other articles and clip
        if (clipAudio) {{ clipAudio.pause(); clipAudio.src = ''; if (currentBtnEl) {{ currentBtnEl.classList.remove('playing'); currentBtnEl = null; }} }}
        for (var i = 0; i < audios.length; i++) {{
          if (i !== artIdx && !audios[i].paused) {{
            audios[i].pause();
            resetArticleUI(i);
          }}
        }}
        a.currentTime = offsets[sentIdx];
        highlightSentence(artIdx, sentIdx);
        currentArtIdx = artIdx;
        currentSentenceIdx = sentIdx;
        if (a.paused) {{
          a.play().then(function() {{
            var btn = document.getElementById('playBtn-' + artIdx);
            if (btn) btn.innerHTML = '&#10074;&#10074;';
          }}).catch(function(e) {{ console.error(e); }});
        }}
      }}
    }});
  }});

  window.toggleTranslation = function(idx) {{
    var cnText = document.getElementById('cnText-' + idx);
    var toggle = document.getElementById('transToggle-' + idx);
    if (cnText.style.display === 'none') {{
      cnText.style.display = 'block';
      toggle.innerHTML = '&#128257; Hide Chinese Translation';
      toggle.classList.add('active');
    }} else {{
      cnText.style.display = 'none';
      toggle.innerHTML = '&#128257; Show Chinese Translation';
      toggle.classList.remove('active');
    }}
  }};

  window.playWord = function(artIdx, wordIdx, btnEl) {{
    // Stop main audio
    if (!audios[artIdx].paused) {{
      audios[artIdx].pause();
      resetArticleUI(artIdx);
    }}
    if (clipAudio) {{ clipAudio.pause(); clipAudio.src = ''; }}
    if (currentBtnEl) currentBtnEl.classList.remove('playing');
    currentBtnEl = btnEl;
    btnEl.classList.add('playing');
    clipAudio = new Audio(ARTICLES[artIdx].wordFiles[wordIdx]);
    clipAudio.playbackRate = 0.85;
    clipAudio.onended = function() {{ btnEl.classList.remove('playing'); currentBtnEl = null; }};
    clipAudio.onerror = function() {{ btnEl.classList.remove('playing'); currentBtnEl = null; }};
    clipAudio.play().catch(function(e) {{ console.error(e); }});
  }};
}})();
</script>
</body>
</html>'''

    return html


def update_news_registry_and_index(script_dir, news_data):
    """Update news registry and rebuild index.html with both news and practice articles."""
    date_str = news_data["date"]
    news_registry_path = os.path.join(script_dir, NEWS_REGISTRY_FILE)

    # Load existing news registry
    if os.path.exists(news_registry_path):
        with open(news_registry_path, "r", encoding="utf-8") as f:
            news_registry = json.load(f)
    else:
        news_registry = []

    # Build news entry
    news_entry = {
        "date": date_str,
        "file": f"english-news-{date_str}.html",
        "articles": [{"title": a["title"], "category": a.get("category", "News")} for a in news_data["articles"]],
        "article_count": len(news_data["articles"]),
    }

    # Remove existing entry for same date, then add
    news_registry = [e for e in news_registry if e["date"] != date_str]
    news_registry.append(news_entry)
    news_registry.sort(key=lambda e: e["date"])

    with open(news_registry_path, "w", encoding="utf-8") as f:
        json.dump(news_registry, f, ensure_ascii=False, indent=2)

    # Load practice registry
    practice_registry_path = os.path.join(script_dir, PRACTICE_REGISTRY_FILE)
    if os.path.exists(practice_registry_path):
        with open(practice_registry_path, "r", encoding="utf-8") as f:
            practice_registry = json.load(f)
    else:
        practice_registry = []

    # Build index.html with both sections
    # News cards
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

    # Practice cards
    practice_cards_html = ""
    for e in reversed(practice_registry):
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
        practice_cards_html += f'''    <a class="card" href="{html_module.escape(e["file"])}">
      <div class="card-day">Day {e["day"]}</div>
      <div class="card-date">{html_module.escape(date_display)}<span class="card-weekday">{html_module.escape(weekday)}</span></div>
      <div class="card-title">{html_module.escape(e["title"])}</div>
      <div class="card-tag" style="color: {tag_color}; background: {tag_bg};">{html_module.escape(e.get("scenario", ""))}</div>
    </a>
'''

    total_practice = len(practice_registry)
    total_news = len(news_registry)

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
  .empty {{ text-align: center; padding: 40px 20px; color: #aaa; }}
  .footer {{ text-align: center; padding: 40px 20px; color: #aaa; font-size: 13px; }}
</style>
</head>
<body>
  <div class="hero">
    <h1>Daily English Practice</h1>
    <p>Read aloud every day to build your fluency and natural sense of the language.<br>News articles help you stay informed while improving your English.</p>
    <div class="stats">
      <div class="stat"><div class="stat-num">{total_practice}</div><div class="stat-label">Practice Days</div></div>
      <div class="stat"><div class="stat-num">{total_news}</div><div class="stat-label">News Days</div></div>
      <div class="stat"><div class="stat-num">&#127881;</div><div class="stat-label">Keep Going</div></div>
    </div>
  </div>
  {"<div class=\"section-header news\"><span class=\"icon\">&#128240;</span><h2>Daily News</h2></div>" if news_cards_html else ""}
  {("<div class=\"grid\">" + news_cards_html + "  </div>") if news_cards_html else ""}
  <div class="section-header"><span class="icon">&#128221;</span><h2>Speaking Practice</h2></div>
  <div class="grid">
{practice_cards_html}  </div>
  <div class="footer">Neural TTS by Microsoft Aria &middot; Practice makes perfect</div>
</body>
</html>'''

    index_path = os.path.join(script_dir, "index.html")
    with open(index_path, "w", encoding="utf-8") as f:
        f.write(index_html)

    print(f"Index updated: {index_path} ({total_practice} practice, {total_news} news)")
    return index_path


async def main():
    if len(sys.argv) < 2:
        print("Usage: python generate_news.py news.json")
        sys.exit(1)

    json_path = sys.argv[1]
    script_dir = os.path.dirname(os.path.abspath(json_path))

    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    date_str = data["date"]
    articles = data["articles"]

    print(f"News date: {date_str}")
    print(f"Articles: {len(articles)}")
    for i, a in enumerate(articles):
        print(f"  [{i}] {a['title']} ({len(a['sentences'])} sentences)")
    print()

    # Create audio directory
    audio_dir = os.path.join(script_dir, "audio", f"news-{date_str}")
    os.makedirs(audio_dir, exist_ok=True)
    audio_rel_dir = f"audio/news-{date_str}"

    # Generate audio for each article
    all_audio = []
    for art_idx, article in enumerate(articles):
        print(f"\nProcessing Article {art_idx}: {article['title']}")
        audio_files = await generate_article_audio(article, audio_dir, art_idx)

        # Build combined audio
        num_sentences = len(article["sentences"])
        offsets, total, full_file = build_combined_audio(audio_dir, art_idx, num_sentences)

        all_audio.append({
            "sentences": audio_files["sentences"],
            "words": audio_files["words"],
            "offsets": offsets,
            "total_duration": total,
            "full_file": full_file,
        })

    # Build HTML
    html = build_html(data, all_audio, audio_rel_dir)
    output_path = os.path.join(script_dir, f"english-news-{date_str}.html")
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html)

    print(f"\nNews HTML written to: {output_path}")
    print(f"Audio files in: {audio_dir}")

    # Update registry and index
    update_news_registry_and_index(script_dir, data)


if __name__ == "__main__":
    asyncio.run(main())
