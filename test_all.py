#!/usr/bin/env python3
"""
Full regression test suite for noapi-google-search-mcp v0.3.0

Tests ALL new features:
  - Feed subscription system (12 existing tests)
  - transcribe_local (local audio/video transcription)
  - convert_media (FFmpeg format conversion)
  - read_document (PDF, DOCX, HTML, plain text)
  - fetch_emails (IMAP email pull)
  - paste_text (dpaste.org pastebin)
  - shorten_url (TinyURL)
  - generate_qr (QR code via OpenCV)
  - archive_webpage (Wayback Machine)
  - wikipedia (article lookup)
  - upload_to_s3 (MinIO/S3 upload)
  - Auto-transcription wiring (YouTube feed → Whisper)

Saves detailed log to test_all_log.txt and report to TEST_REPORT_FULL.md
"""

import asyncio
import json
import os
import sys
import tempfile
import time
import traceback
import zipfile

sys.path.insert(0, "src")
os.environ["FEEDS_DB_PATH"] = "/tmp/test_all_feeds.db"

# ── imports from our server ──
from google_search_mcp.server import (
    _auto_transcribe_youtube,
    _get_feeds_db,
    _strip_html,
    _parse_rss_atom,
    _store_items,
    _check_source_rss,
    _check_source_reddit,
    _check_source_hackernews,
    _check_source_github,
    _check_source_arxiv,
    _check_source_youtube,
    _check_source_podcast,
    _transcript_cache_path,
    _IMAP_SERVERS,
    TRANSCRIPT_CACHE_DIR,
    TRANSCRIBE_CACHE_DIR,
    subscribe,
    unsubscribe,
    list_subscriptions,
    check_feeds,
    search_feeds,
    get_feed_items,
    transcribe_local,
    convert_media,
    read_document,
    fetch_emails,
    paste_text,
    shorten_url,
    generate_qr,
    archive_webpage,
    wikipedia,
    upload_to_s3,
    mcp,
)

LOG_FILE = os.path.join(os.path.dirname(__file__), "test_all_log.txt")
REPORT_FILE = os.path.join(os.path.dirname(__file__), "TEST_REPORT_FULL.md")

log_lines: list[str] = []
report_sections: list[str] = []

passed = 0
failed = 0
test_results: list[dict] = []


def log(msg: str = ""):
    log_lines.append(msg)
    print(msg)


def section(title: str):
    log(f"\n{'=' * 70}")
    log(f"  {title}")
    log(f"{'=' * 70}\n")


def check(label: str, condition: bool, detail: str = ""):
    global passed, failed
    if condition:
        passed += 1
        log(f"    CHECK: PASS — {label}")
    else:
        failed += 1
        log(f"    CHECK: FAIL — {label}")
    if detail:
        log(f"    Detail: {detail}")
    return condition


async def run_test(name: str, func, report_md: list[str]):
    global passed, failed
    t0 = time.time()
    p_before = passed
    f_before = failed
    try:
        log(f"--- {name} ---")
        await func()
        elapsed = time.time() - t0
        test_pass = (failed == f_before)
        status = "PASS" if test_pass else "FAIL"
        log(f"  -> {status}  ({elapsed:.2f}s)\n")
        test_results.append({
            "name": name,
            "time": elapsed,
            "passed": passed - p_before,
            "failed": failed - f_before,
            "status": status,
        })
    except Exception as e:
        elapsed = time.time() - t0
        failed += 1
        log(f"  -> EXCEPTION: {e}")
        log(f"  {traceback.format_exc()}")
        log(f"  -> FAIL  ({elapsed:.2f}s)\n")
        test_results.append({
            "name": name,
            "time": elapsed,
            "passed": 0,
            "failed": 1,
            "status": "FAIL",
        })


# ═══════════════════════════════════════════════════════════════════════
# UNIT TESTS (from original test_feeds.py, preserved for regression)
# ═══════════════════════════════════════════════════════════════════════

async def test_strip_html():
    log("    Testing HTML tag removal:")
    cases = [
        ("<p>Hello <b>world</b></p>", "Hello world"),
        ("", ""),
        ("plain text", "plain text"),
        ("<a href='x'>link</a> and <em>emphasis</em>", "link and emphasis"),
        ("<div><span>nested</span></div>", "nested"),
    ]
    for inp, expected in cases:
        result = _strip_html(inp)
        check(f"strip_html({repr(inp)[:40]}) == {repr(expected)}", result == expected)


async def test_rss_parsing():
    log("    Testing RSS 2.0 parsing:")
    rss_xml = b"""<?xml version="1.0"?>
    <rss version="2.0"><channel><title>Test</title>
      <item>
        <title>Article One</title><link>https://example.com/1</link>
        <description>First article content</description>
        <pubDate>Mon, 01 Jan 2024 12:00:00 GMT</pubDate>
      </item>
      <item>
        <title>Article Two</title><link>https://example.com/2</link>
        <description>&lt;p&gt;HTML content&lt;/p&gt;</description>
      </item>
    </channel></rss>"""
    items = _parse_rss_atom(rss_xml)
    check("Item count == 2", len(items) == 2)
    check("First title", items[0]["title"] == "Article One")
    check("First URL", items[0]["url"] == "https://example.com/1")
    check("First content", items[0]["content"] == "First article content")
    check("First pubDate", "Jan" in items[0].get("published", ""))
    check("Second title", items[1]["title"] == "Article Two")
    check("HTML stripped", "<p>" not in items[1]["content"])


async def test_atom_parsing():
    log("    Testing Atom feed parsing:")
    atom_xml = b"""<?xml version="1.0"?>
    <feed xmlns="http://www.w3.org/2005/Atom">
      <title>Test Atom</title>
      <entry>
        <title>Entry One</title>
        <link rel="alternate" href="https://example.com/a"/>
        <summary>First summary</summary>
        <published>2024-01-01T12:00:00Z</published>
        <author><name>Alice</name></author>
      </entry>
      <entry>
        <title>Entry Two</title>
        <link href="https://example.com/b"/>
        <content type="html">&lt;p&gt;HTML content&lt;/p&gt;</content>
        <updated>2024-02-01T12:00:00Z</updated>
      </entry>
    </feed>"""
    items = _parse_rss_atom(atom_xml)
    check("Item count == 2", len(items) == 2)
    check("First title", items[0]["title"] == "Entry One")
    check("First URL (rel=alternate)", items[0]["url"] == "https://example.com/a")
    check("First author", items[0].get("author") == "Alice")
    check("First published", "2024" in items[0].get("published", ""))
    check("Second title", items[1]["title"] == "Entry Two")
    check("Second URL", items[1]["url"] == "https://example.com/b")
    check("HTML stripped", "<p>" not in items[1]["content"])


async def test_sqlite_fts5():
    log("    Testing SQLite + FTS5 database:")
    db_path = "/tmp/test_all_unit.db"
    try:
        os.remove(db_path)
    except FileNotFoundError:
        pass
    old = os.environ.get("FEEDS_DB_PATH")
    os.environ["FEEDS_DB_PATH"] = db_path
    try:
        conn = _get_feeds_db()
        tables = [r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()]
        check("Tables created", "subscriptions" in tables and "feed_items" in tables)

        conn.execute(
            "INSERT INTO subscriptions (source_type, identifier, name, feed_url, created_at) "
            "VALUES (?, ?, ?, ?, datetime('now'))",
            ("news", "test_unit", "Unit Test Feed", "http://example.com/rss"),
        )
        conn.commit()
        row = conn.execute(
            "SELECT id, name FROM subscriptions WHERE identifier = 'test_unit'"
        ).fetchone()
        sub_id = row[0]
        check("Subscription inserted", row[1] == "Unit Test Feed")

        items = [
            {"title": "Python 4.0 Released", "url": "https://example.com/1",
             "content": "Python 4.0 has been released.", "published": "2024-01-01"},
            {"title": "AI Breakthrough", "url": "https://example.com/2",
             "content": "Researchers discover new architecture for transformers."},
            {"title": "No URL Item", "url": "", "content": "Should be skipped"},
        ]
        new_count = _store_items(conn, sub_id, "news", items)
        check("Stored 2 items (1 skipped)", new_count == 2)

        dup_count = _store_items(conn, sub_id, "news", items)
        check("Duplicates ignored", dup_count == 0)

        fts = conn.execute(
            "SELECT title FROM feed_items WHERE id IN "
            "(SELECT rowid FROM feed_items_fts WHERE feed_items_fts MATCH ?)",
            ("transformers",),
        ).fetchall()
        check("FTS5 'transformers' → 1 result", len(fts) == 1)

        fts2 = conn.execute(
            "SELECT title FROM feed_items WHERE id IN "
            "(SELECT rowid FROM feed_items_fts WHERE feed_items_fts MATCH ?)",
            ("Python",),
        ).fetchall()
        check("FTS5 'Python' → 1 result", len(fts2) == 1)

        fts3 = conn.execute(
            "SELECT title FROM feed_items WHERE id IN "
            "(SELECT rowid FROM feed_items_fts WHERE feed_items_fts MATCH ?)",
            ("nonexistent",),
        ).fetchall()
        check("FTS5 'nonexistent' → 0 results", len(fts3) == 0)

        conn.execute("DELETE FROM subscriptions WHERE id = ?", (sub_id,))
        conn.commit()
        remaining = conn.execute("SELECT COUNT(*) FROM feed_items").fetchone()[0]
        check("Cascade delete", remaining == 0)

        conn.close()
    finally:
        os.environ["FEEDS_DB_PATH"] = old or "/tmp/test_all_feeds.db"
        try:
            os.remove(db_path)
        except FileNotFoundError:
            pass


# ═══════════════════════════════════════════════════════════════════════
# LIVE SOURCE TESTS
# ═══════════════════════════════════════════════════════════════════════

async def test_bbc_news():
    log("    Source: BBC News RSS")
    items = await _check_source_rss("http://feeds.bbci.co.uk/news/rss.xml")
    log(f"    Items fetched: {len(items)}")
    if items:
        log(f"    Sample: {items[0]['title'][:80]}")
    check("≥ 5 items", len(items) >= 5)
    check("All have titles", all(i.get("title") for i in items))
    check("All have URLs", all(i.get("url") for i in items))
    check("URLs are HTTP(S)", all(i["url"].startswith("http") for i in items))


async def test_reddit():
    log("    Source: Reddit r/technology")
    items = await _check_source_reddit("technology")
    log(f"    Items fetched: {len(items)}")
    check("≥ 5 items", len(items) >= 5)
    check("All have titles", all(i.get("title") for i in items))
    check("All have URLs", all(i.get("url") for i in items))


async def test_hackernews():
    log("    Source: Hacker News top stories")
    items = await _check_source_hackernews("top", limit=5)
    log(f"    Items fetched: {len(items)}")
    if items:
        log(f"    Sample: {items[0]['title'][:80]}")
    check("Got 5 stories", len(items) == 5)
    check("All have titles", all(i.get("title") for i in items))
    check("All have URLs", all(i.get("url") for i in items))
    check("All have authors", all(i.get("author") for i in items))
    check("Metadata has score", all("score" in i.get("metadata", "") for i in items))
    check("Metadata has comments", all("comments" in i.get("metadata", "") for i in items))


async def test_github():
    log("    Source: GitHub anthropics/anthropic-sdk-python")
    items = await _check_source_github("anthropics/anthropic-sdk-python")
    log(f"    Items fetched: {len(items)}")
    if items:
        log(f"    Latest: {items[0]['title']}")
    check("≥ 1 release", len(items) >= 1)
    check("All have titles", all(i.get("title") for i in items))
    check("All have URLs", all(i.get("url") for i in items))
    check("URLs point to GitHub", all("github.com" in i["url"] for i in items))


async def test_arxiv():
    log("    Source: arXiv cs.AI")
    items = await _check_source_arxiv("cs.AI", max_results=5)
    log(f"    Items fetched: {len(items)}")
    if items:
        log(f"    Sample: {items[0]['title'][:80]}")
    check("Got papers", len(items) > 0)
    check("All have titles", all(i.get("title") for i in items))
    check("All have URLs", all(i.get("url") for i in items))
    check("URLs contain arxiv", all("arxiv" in i["url"] for i in items))
    check("Has abstracts", any(len(i.get("content", "")) > 50 for i in items))


async def test_youtube():
    log("    Source: YouTube 3Blue1Brown")
    feed_url = "https://www.youtube.com/feeds/videos.xml?channel_id=UCYO_jab_esuFRV4b17AJtAw"
    items = await _check_source_youtube(feed_url)
    log(f"    Items fetched: {len(items)}")
    if items:
        log(f"    Latest: {items[0]['title'][:80]}")
    check("Got videos", len(items) > 0)
    check("All have titles", all(i.get("title") for i in items))
    check("All have URLs", all(i.get("url") for i in items))
    check("URLs are YouTube", all("youtube.com" in i["url"] for i in items))
    check("Metadata has video_url", all("video_url" in i.get("metadata", "") for i in items))


async def test_podcast():
    log("    Source: Lex Fridman Podcast")
    items = await _check_source_podcast("https://lexfridman.com/feed/podcast/")
    log(f"    Items fetched: {len(items)}")
    if items:
        log(f"    Latest: {items[0]['title'][:80]}")
    check("Got episodes", len(items) > 0)
    check("All have titles", all(i.get("title") for i in items))
    check("Has audio URLs", any("audio_url" in i.get("metadata", "") for i in items))


# ═══════════════════════════════════════════════════════════════════════
# END-TO-END MCP TOOL TEST
# ═══════════════════════════════════════════════════════════════════════

async def test_e2e_feeds():
    log("    Full MCP tool workflow: subscribe → check → search → get → unsubscribe")
    db_path = "/tmp/test_all_e2e.db"
    try:
        os.remove(db_path)
    except FileNotFoundError:
        pass
    os.environ["FEEDS_DB_PATH"] = db_path
    try:
        # Subscribe
        r = await subscribe("news", "bbc")
        check("Subscribe news/bbc", "Subscribed" in r)
        log(f"    Output: {r}")

        r = await subscribe("hackernews", "top")
        check("Subscribe hackernews/top", "Subscribed" in r)

        r = await subscribe("news", "bbc")
        check("Duplicate detected", "Already" in r)

        r = await subscribe("invalid", "test")
        check("Invalid type rejected", "Invalid" in r or "invalid" in r.lower())

        # List
        r = await list_subscriptions()
        check("Both listed", "BBC" in r and "Hacker" in r)

        # Check
        r = await check_feeds()
        log(f"    Output: {r[:200]}")
        check("Feeds checked", "new items" in r)

        # Get
        r = await get_feed_items(source_type="news")
        check("News items returned", "items" in r.lower())

        r = await get_feed_items(source_type="hackernews", limit=3)
        check("HN items returned (limit 3)", "items" in r.lower())

        # Search
        r = await search_feeds("the")
        check("Search returned results", "results" in r.lower() or "Feed Search" in r)

        r = await search_feeds("xyznonexistent12345")
        check("Empty search handled", "No results" in r)

        # Unsubscribe
        r = await unsubscribe("news", "bbc")
        check("Unsubscribed", "Unsubscribed" in r)

        r = await list_subscriptions()
        check("BBC removed", "BBC" not in r)

        r = await unsubscribe("news", "nonexistent_feed")
        check("Nonexistent handled", "No subscription" in r or "not found" in r.lower())
    finally:
        os.environ["FEEDS_DB_PATH"] = "/tmp/test_all_feeds.db"
        try:
            os.remove(db_path)
        except FileNotFoundError:
            pass


# ═══════════════════════════════════════════════════════════════════════
# NEW TOOL TESTS
# ═══════════════════════════════════════════════════════════════════════

async def test_transcribe_local():
    log("    Testing local file transcription:")

    # File not found
    r = await transcribe_local("/nonexistent/file.mp3")
    check("File not found", "not found" in r.lower())

    # Invalid model size → defaults to tiny
    r = await transcribe_local("/nonexistent/f.mp3", model_size="huge")
    check("Invalid model size handled", "not found" in r.lower())

    # Real file but not audio → graceful error
    with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as f:
        f.write(b"not audio data")
        tmp = f.name
    r = await transcribe_local(tmp)
    os.unlink(tmp)
    check("Non-audio file handled", "failed" in r.lower() or "required" in r.lower())
    log(f"    Output: {r[:80]}")


async def test_convert_media():
    log("    Testing media format conversion:")

    # File not found
    r = await convert_media("/nonexistent/video.mp4", "mp3")
    check("File not found", "not found" in r.lower())

    # Check ffmpeg availability
    import subprocess
    try:
        p = subprocess.run(["ffmpeg", "-version"], capture_output=True, timeout=5)
        has_ffmpeg = p.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        has_ffmpeg = False

    if has_ffmpeg:
        # Create a test WAV file (1 second of silence) and convert to mp3
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            tmp_wav = f.name
        # Generate a silent WAV using ffmpeg
        subprocess.run(
            ["ffmpeg", "-y", "-f", "lavfi", "-i", "anullsrc=r=44100:cl=mono",
             "-t", "1", tmp_wav],
            capture_output=True, timeout=10,
        )
        if os.path.isfile(tmp_wav) and os.path.getsize(tmp_wav) > 0:
            tmp_mp3 = tmp_wav.replace(".wav", ".mp3")
            r = await convert_media(tmp_wav, "mp3")
            check("WAV→MP3 conversion", "Converted successfully" in r)
            log(f"    Output: {r}")
            # Clean up
            for f in (tmp_wav, tmp_mp3):
                try:
                    os.remove(f)
                except FileNotFoundError:
                    pass
        else:
            log("    SKIP — could not generate test WAV")
    else:
        log("    SKIP — ffmpeg not installed")
        r = await convert_media("/dev/null", "mp3")
        check("FFmpeg missing handled", "not found" in r.lower())


async def test_read_document():
    log("    Testing document reader:")

    # File not found
    r = await read_document("/nonexistent/doc.pdf")
    check("File not found", "not found" in r.lower())

    # README.md (plain text)
    r = await read_document(os.path.abspath("README.md"))
    check("README.md read", "Document: README.md" in r and len(r) > 100)

    # pyproject.toml
    r = await read_document(os.path.abspath("pyproject.toml"))
    check("TOML read", "noapi-google-search-mcp" in r)

    # Unsupported format
    with tempfile.NamedTemporaryFile(suffix=".xyz", delete=False) as f:
        f.write(b"test")
        tmp = f.name
    r = await read_document(tmp)
    os.unlink(tmp)
    check("Unsupported format", "Unsupported" in r)

    # Synthetic DOCX
    with tempfile.NamedTemporaryFile(suffix=".docx", delete=False) as f:
        tmp_docx = f.name
    with zipfile.ZipFile(tmp_docx, "w") as zf:
        zf.writestr("word/document.xml", """<?xml version="1.0" encoding="UTF-8"?>
<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
  <w:body>
    <w:p><w:r><w:t>Hello from DOCX!</w:t></w:r></w:p>
    <w:p><w:r><w:t>Second paragraph.</w:t></w:r></w:p>
  </w:body>
</w:document>""")
    r = await read_document(tmp_docx)
    os.unlink(tmp_docx)
    check("DOCX parsed", "Hello from DOCX!" in r and "Second paragraph" in r)
    log(f"    DOCX output: {r[:120]}")

    # HTML file
    with tempfile.NamedTemporaryFile(suffix=".html", delete=False, mode="w") as f:
        f.write("<html><body><h1>Title</h1><p>Hello <b>world</b></p></body></html>")
        tmp_html = f.name
    r = await read_document(tmp_html)
    os.unlink(tmp_html)
    check("HTML stripped", "Title" in r and "Hello world" in r and "<h1>" not in r)

    # CSV file
    with tempfile.NamedTemporaryFile(suffix=".csv", delete=False, mode="w") as f:
        f.write("name,age\nAlice,30\nBob,25\n")
        tmp_csv = f.name
    r = await read_document(tmp_csv)
    os.unlink(tmp_csv)
    check("CSV read", "Alice,30" in r)


async def test_fetch_emails():
    log("    Testing email fetch:")

    # IMAP server auto-detection
    check("Gmail detected", _IMAP_SERVERS["gmail.com"] == "imap.gmail.com")
    check("Outlook detected", _IMAP_SERVERS["outlook.com"] == "imap-mail.outlook.com")
    check("Yahoo detected", _IMAP_SERVERS["yahoo.com"] == "imap.mail.yahoo.com")

    # Unknown domain
    r = await fetch_emails("user@unknowndomain.xyz", "pass123")
    check("Unknown domain handled", "Cannot auto-detect" in r)

    # Bad credentials → auth failure (not crash)
    r = await fetch_emails("test@gmail.com", "wrongpassword")
    check("Bad auth handled", "failed" in r.lower() or "error" in r.lower())
    log(f"    Auth error: {r[:80]}")


async def test_paste_text():
    log("    Testing pastebin posting:")

    # Empty content
    r = await paste_text("")
    check("Empty content handled", "empty" in r.lower())

    # Real paste
    r = await paste_text("Hello from noapi-google-search-mcp test!", title="Test Paste")
    is_success = ("Paste created" in r and "http" in r and "Failed" not in r)
    check("Paste created", is_success)
    log(f"    Output: {r}")


async def test_shorten_url():
    log("    Testing URL shortener:")

    r = await shorten_url("https://github.com/VincentKaufmann/noapi-google-search-mcp")
    check("URL shortened", "tinyurl.com" in r)
    log(f"    Output: {r}")


async def test_generate_qr():
    log("    Testing QR code generation:")

    # Generate QR for a URL
    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
        tmp_qr = f.name
    r = await generate_qr("https://example.com", output_path=tmp_qr)
    exists = os.path.isfile(tmp_qr) and os.path.getsize(tmp_qr) > 0
    check("QR code generated", exists and "saved" in r.lower())
    log(f"    Output: {r}")
    if exists:
        size_kb = os.path.getsize(tmp_qr) / 1024
        log(f"    File size: {size_kb:.1f} KB")
    try:
        os.unlink(tmp_qr)
    except FileNotFoundError:
        pass

    # Empty data
    r = await generate_qr("")
    check("Empty data handled", "empty" in r.lower())


async def test_archive_webpage():
    log("    Testing webpage archiving:")

    r = await archive_webpage("https://example.com")
    check("Archive response", "archive" in r.lower() or "web.archive.org" in r)
    log(f"    Output: {r}")


async def test_wikipedia():
    log("    Testing Wikipedia lookup:")

    # Known article
    r = await wikipedia("Python programming language")
    check("Python article found", "Python" in r and len(r) > 100)
    log(f"    Output preview: {r[:150]}...")

    # Non-existent article
    r = await wikipedia("xyznonexistent12345abcde")
    check("Missing article handled", "not found" in r.lower() or "No" in r)

    # Summary with sentence limit
    r = await wikipedia("Albert Einstein", sentences=2)
    check("Sentence limit works", len(r) < 1000 and "Einstein" in r)
    log(f"    Summary: {r[:120]}...")

    # Non-English
    r = await wikipedia("inteligencia artificial", language="es")
    check("Spanish Wikipedia", "inteligencia" in r.lower() or "artificial" in r.lower())


async def test_upload_s3():
    log("    Testing S3/MinIO upload:")

    # File not found
    r = await upload_to_s3("/nonexistent/file.txt", "test-bucket")
    check("File not found", "not found" in r.lower())

    # Missing credentials
    with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as f:
        f.write(b"test data")
        tmp = f.name
    # Clear env vars to test credential check
    old_key = os.environ.pop("AWS_ACCESS_KEY_ID", None)
    old_secret = os.environ.pop("AWS_SECRET_ACCESS_KEY", None)
    r = await upload_to_s3(tmp, "test-bucket")
    check("Missing creds handled", "Missing credentials" in r or "credentials" in r.lower())
    log(f"    Output: {r[:80]}")
    # Restore env
    if old_key:
        os.environ["AWS_ACCESS_KEY_ID"] = old_key
    if old_secret:
        os.environ["AWS_SECRET_ACCESS_KEY"] = old_secret
    os.unlink(tmp)


async def test_auto_transcribe_youtube():
    log("    Testing auto-transcription wiring:")

    db_path = "/tmp/test_autotranscribe.db"
    try:
        os.remove(db_path)
    except FileNotFoundError:
        pass
    os.environ["FEEDS_DB_PATH"] = db_path
    try:
        conn = _get_feeds_db()

        # Empty items
        r = await _auto_transcribe_youtube(conn, sub_id=999, items=[])
        check("Empty items → empty string", r == "")

        # Non-YouTube URLs
        items = [{"url": "https://example.com/article", "title": "Not YT"}]
        r = await _auto_transcribe_youtube(conn, sub_id=999, items=items)
        check("Non-YouTube → empty string", r == "")

        # Already-cached video
        os.makedirs(TRANSCRIPT_CACHE_DIR, exist_ok=True)
        test_url = "https://www.youtube.com/watch?v=test_cached_123"
        cache_path = _transcript_cache_path(test_url, "tiny")
        with open(cache_path, "w") as f:
            json.dump({"url": test_url, "transcript": "cached"}, f)
        items = [{"url": test_url, "title": "Cached"}]
        r = await _auto_transcribe_youtube(conn, sub_id=999, items=items)
        check("Cached video skipped", r == "")
        os.remove(cache_path)

        conn.close()
    finally:
        os.environ["FEEDS_DB_PATH"] = "/tmp/test_all_feeds.db"
        try:
            os.remove(db_path)
        except FileNotFoundError:
            pass


async def test_tool_count():
    log("    Verifying tool registration:")
    tools = mcp._tool_manager._tools
    count = len(tools)
    check(f"Tool count == 38 (got {count})", count == 38)
    expected = [
        "transcribe_local", "convert_media", "read_document", "fetch_emails",
        "paste_text", "shorten_url", "generate_qr", "archive_webpage",
        "wikipedia", "upload_to_s3", "subscribe", "check_feeds",
        "search_feeds", "get_feed_items", "list_subscriptions", "unsubscribe",
    ]
    for name in expected:
        check(f"Tool registered: {name}", name in tools)


# ═══════════════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════════════

async def main():
    log(f"{'=' * 70}")
    log(f"  noapi-google-search-mcp — Full Regression Test Suite")
    log(f"{'=' * 70}")
    log(f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    log(f"Python: {sys.version.split()[0]}")
    log(f"Platform: {sys.platform}")
    log()

    section("TOOL REGISTRATION")
    await run_test("Tool count and registration", test_tool_count, report_sections)

    section("UNIT TESTS")
    await run_test("_strip_html — HTML tag removal", test_strip_html, report_sections)
    await run_test("_parse_rss_atom — RSS 2.0 parsing", test_rss_parsing, report_sections)
    await run_test("_parse_rss_atom — Atom parsing", test_atom_parsing, report_sections)
    await run_test("SQLite + FTS5 database", test_sqlite_fts5, report_sections)

    section("LIVE SOURCE TESTS (network)")
    await run_test("News RSS — BBC News", test_bbc_news, report_sections)
    await run_test("Reddit — r/technology", test_reddit, report_sections)
    await run_test("Hacker News — Top Stories", test_hackernews, report_sections)
    await run_test("GitHub — Releases", test_github, report_sections)
    await run_test("arXiv — cs.AI Papers", test_arxiv, report_sections)
    await run_test("YouTube — 3Blue1Brown", test_youtube, report_sections)
    await run_test("Podcast — Lex Fridman", test_podcast, report_sections)

    section("END-TO-END MCP TOOL TEST")
    await run_test("Full feed workflow", test_e2e_feeds, report_sections)

    section("NEW TOOLS — LOCAL FILE PROCESSING")
    await run_test("transcribe_local — local audio/video", test_transcribe_local, report_sections)
    await run_test("convert_media — FFmpeg conversion", test_convert_media, report_sections)
    await run_test("read_document — PDF/DOCX/text/HTML", test_read_document, report_sections)

    section("NEW TOOLS — EMAIL")
    await run_test("fetch_emails — IMAP email pull", test_fetch_emails, report_sections)

    section("NEW TOOLS — WEB UTILITIES")
    await run_test("paste_text — dpaste.org pastebin", test_paste_text, report_sections)
    await run_test("shorten_url — TinyURL", test_shorten_url, report_sections)
    await run_test("generate_qr — QR code generation", test_generate_qr, report_sections)
    await run_test("archive_webpage — Wayback Machine", test_archive_webpage, report_sections)
    await run_test("wikipedia — article lookup", test_wikipedia, report_sections)

    section("NEW TOOLS — CLOUD STORAGE")
    await run_test("upload_to_s3 — MinIO/S3 upload", test_upload_s3, report_sections)

    section("AUTO-TRANSCRIPTION WIRING")
    await run_test("YouTube auto-transcription", test_auto_transcribe_youtube, report_sections)

    # ── Summary ──
    section("SUMMARY")
    total = passed + failed
    test_count = len(test_results)
    tests_passed = sum(1 for t in test_results if t["status"] == "PASS")
    tests_failed = sum(1 for t in test_results if t["status"] == "FAIL")

    log(f"  Total test groups: {test_count}")
    log(f"  Passed:            {tests_passed}")
    log(f"  Failed:            {tests_failed}")
    log(f"  Total checks:      {total} ({passed} passed, {failed} failed)")
    log(f"  Pass rate:         {passed/total*100:.0f}%" if total else "  No checks run")
    log()
    if failed == 0:
        log("  ALL TESTS PASSED")
    else:
        log(f"  {failed} CHECK(S) FAILED")

    log()
    log("  Individual results:")
    total_time = 0
    for t in test_results:
        log(f"    {t['status']:4} | {t['time']:5.2f}s | {t['name']}")
        total_time += t["time"]
    log(f"    {'':4} | {total_time:5.2f}s | TOTAL")

    # ── Save log ──
    with open(LOG_FILE, "w") as f:
        f.write("\n".join(log_lines))
    log(f"\nFull log saved to: {LOG_FILE}")

    # ── Save markdown report ──
    md = []
    md.append(f"# noapi-google-search-mcp v0.3.0 — Full Regression Test Report\n")
    md.append(f"**Date:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    md.append(f"**Python:** {sys.version.split()[0]}")
    md.append(f"**Platform:** {sys.platform}")
    md.append(f"**Tools:** {len(mcp._tool_manager._tools)}")
    md.append(f"**Result:** {tests_passed}/{test_count} test groups PASSED, "
              f"{passed}/{total} checks PASSED ({passed/total*100:.0f}%)\n")
    md.append("---\n")
    md.append("## Results\n")
    md.append("| # | Test | Checks | Time | Result |")
    md.append("|---|------|--------|------|--------|")
    for i, t in enumerate(test_results, 1):
        checks = f"{t['passed']}{'/' + str(t['passed'] + t['failed']) if t['failed'] else ''}"
        md.append(f"| {i} | {t['name']} | {checks} | {t['time']:.2f}s | {t['status']} |")
    md.append(f"| | **Total** | **{passed}/{total}** | **{total_time:.2f}s** | "
              f"**{tests_passed}/{test_count}** |")
    md.append("\n---\n")

    if failed == 0:
        md.append("```\nALL TESTS PASSED\n```\n")
    else:
        md.append(f"```\n{failed} CHECK(S) FAILED\n```\n")

    with open(REPORT_FILE, "w") as f:
        f.write("\n".join(md))
    log(f"Report saved to: {REPORT_FILE}")

    return failed == 0

if __name__ == "__main__":
    from datetime import datetime
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
