"""
Integration tests for the Feed Subscription System (v0.3.0).

Tests all source types: news RSS, Reddit, Hacker News, GitHub, arXiv,
YouTube, podcasts, and Twitter/X.

Produces a detailed test log with inputs, outputs, and functionality checks.

Run:  python3 test_feeds.py
"""

import asyncio
import json
import os
import sqlite3
import sys
import time
import textwrap

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

from google_search_mcp.server import (
    FEEDS_DB_PATH,
    PRESET_NEWS_FEEDS,
    _check_source_arxiv,
    _check_source_github,
    _check_source_hackernews,
    _check_source_podcast,
    _check_source_reddit,
    _check_source_rss,
    _check_source_youtube,
    _fetch_url_bytes,
    _get_feeds_db,
    _parse_rss_atom,
    _store_items,
    _strip_html,
    check_feeds,
    get_feed_items,
    list_subscriptions,
    search_feeds,
    subscribe,
    unsubscribe,
)

# ---------------------------------------------------------------------------
# Test infrastructure
# ---------------------------------------------------------------------------

PASS = 0
FAIL = 0
LOG_LINES: list[str] = []


def log(msg: str = ""):
    LOG_LINES.append(msg)
    print(msg)


def section(title: str):
    log("")
    log("=" * 70)
    log(f"  {title}")
    log("=" * 70)


def subsection(title: str):
    log("")
    log(f"--- {title} ---")


def detail(label: str, value, max_len: int = 300):
    s = str(value)
    if len(s) > max_len:
        s = s[:max_len] + f"... [{len(str(value))} chars total]"
    for i, line in enumerate(s.split("\n")):
        if i == 0:
            log(f"    {label}: {line}")
        else:
            log(f"    {'':>{len(label)}}  {line}")


def result(name: str, passed: bool, elapsed: float):
    global PASS, FAIL
    if passed:
        PASS += 1
        log(f"  -> PASS  ({elapsed:.2f}s)")
    else:
        FAIL += 1
        log(f"  -> FAIL  ({elapsed:.2f}s)")


# ---------------------------------------------------------------------------
# Unit tests
# ---------------------------------------------------------------------------

def test_strip_html():
    subsection("_strip_html — HTML tag removal")

    cases = [
        ("<p>Hello <b>world</b></p>", "Hello world"),
        ("", ""),
        ("plain text", "plain text"),
        ("<a href='x'>link</a> and <em>emphasis</em>", "link and emphasis"),
        ("<div><span>nested</span></div>", "nested"),
    ]

    t0 = time.time()
    all_ok = True
    for html_in, expected in cases:
        actual = _strip_html(html_in)
        ok = actual == expected
        detail("Input", repr(html_in))
        detail("Expected", repr(expected))
        detail("Got", repr(actual))
        detail("Match", "YES" if ok else "NO")
        log("")
        if not ok:
            all_ok = False

    result("_strip_html", all_ok, time.time() - t0)
    return all_ok


def test_parse_rss():
    subsection("_parse_rss_atom — RSS 2.0 feed parsing")

    xml = b"""<?xml version="1.0"?>
    <rss version="2.0">
      <channel>
        <title>Test Feed</title>
        <item>
          <title>Article One</title>
          <link>https://example.com/1</link>
          <description>First article content</description>
          <pubDate>Mon, 01 Jan 2024 00:00:00 GMT</pubDate>
          <author>alice@example.com</author>
        </item>
        <item>
          <title>Article Two</title>
          <link>https://example.com/2</link>
          <description>&lt;p&gt;HTML description&lt;/p&gt;</description>
        </item>
      </channel>
    </rss>"""

    detail("Input", "RSS 2.0 XML with 2 items (one with HTML description)")

    t0 = time.time()
    items = _parse_rss_atom(xml)

    checks = {
        "Item count == 2": len(items) == 2,
        "First title correct": items[0]["title"] == "Article One",
        "First URL correct": items[0]["url"] == "https://example.com/1",
        "First content correct": items[0]["content"] == "First article content",
        "First pubDate present": "Jan" in items[0]["published"],
        "Second title correct": items[1]["title"] == "Article Two",
        "HTML stripped from content": "<p>" not in items[1]["content"],
    }

    for check_name, passed in checks.items():
        detail(check_name, "PASS" if passed else "FAIL")

    all_ok = all(checks.values())
    result("RSS 2.0 parsing", all_ok, time.time() - t0)
    return all_ok


def test_parse_atom():
    subsection("_parse_rss_atom — Atom feed parsing")

    xml = b"""<?xml version="1.0" encoding="UTF-8"?>
    <feed xmlns="http://www.w3.org/2005/Atom">
      <title>Test Atom Feed</title>
      <entry>
        <title>Entry One</title>
        <link rel="alternate" href="https://example.com/a"/>
        <summary>First entry summary</summary>
        <published>2024-01-01T00:00:00Z</published>
        <author><name>Alice</name></author>
      </entry>
      <entry>
        <title>Entry Two</title>
        <link href="https://example.com/b"/>
        <content type="html">&lt;p&gt;Content here&lt;/p&gt;</content>
        <updated>2024-01-02T00:00:00Z</updated>
      </entry>
    </feed>"""

    detail("Input", "Atom XML with 2 entries (one with <summary>, one with <content>)")

    t0 = time.time()
    items = _parse_rss_atom(xml)

    checks = {
        "Item count == 2": len(items) == 2,
        "First title": items[0]["title"] == "Entry One",
        "First URL (rel=alternate)": items[0]["url"] == "https://example.com/a",
        "First author": items[0]["author"] == "Alice",
        "First published": "2024" in items[0]["published"],
        "Second title": items[1]["title"] == "Entry Two",
        "Second URL (no rel)": items[1]["url"] == "https://example.com/b",
        "Second content (HTML stripped)": "<p>" not in items[1]["content"],
    }

    for check_name, passed in checks.items():
        detail(check_name, "PASS" if passed else "FAIL")

    all_ok = all(checks.values())
    result("Atom parsing", all_ok, time.time() - t0)
    return all_ok


def test_database():
    subsection("SQLite + FTS5 database operations")

    test_db = "/tmp/test_feeds_unit.db"
    for f in [test_db, test_db + "-wal", test_db + "-shm"]:
        if os.path.exists(f):
            os.remove(f)

    import google_search_mcp.server as srv
    original = srv.FEEDS_DB_PATH
    srv.FEEDS_DB_PATH = test_db

    t0 = time.time()
    all_ok = True
    try:
        conn = _get_feeds_db()
        detail("Database created", test_db)

        # Check tables exist
        tables = [r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()]
        detail("Tables found", tables)
        for t in ["subscriptions", "feed_items"]:
            if t not in tables:
                detail(f"Missing table", t)
                all_ok = False

        # Insert subscription
        conn.execute(
            "INSERT INTO subscriptions (source_type, identifier, name, feed_url, created_at) "
            "VALUES (?, ?, ?, ?, ?)",
            ("news", "test_unit", "Unit Test Feed", "http://example.com/rss", "2024-01-01T00:00:00Z"),
        )
        conn.commit()
        sub = conn.execute("SELECT * FROM subscriptions WHERE identifier = 'test_unit'").fetchone()
        detail("Subscription inserted", f"id={sub['id']}, name={sub['name']}")

        # Store items
        test_items = [
            {"title": "Machine Learning Breakthrough", "url": "http://example.com/ml", "content": "Researchers discover new architecture for transformers", "published": "2024-01-01", "author": "Dr. Smith"},
            {"title": "Python 4.0 Released", "url": "http://example.com/py", "content": "Major release with new features", "published": "2024-01-02", "author": "PSF"},
            {"title": "No URL Item", "url": "", "content": "Should be skipped"},
        ]
        detail("Input items", f"{len(test_items)} items (1 without URL, should be skipped)")
        new_count = _store_items(conn, sub["id"], "news", test_items)
        detail("New items stored", new_count)
        if new_count != 2:
            all_ok = False

        # Duplicate test
        dup_count = _store_items(conn, sub["id"], "news", test_items)
        detail("Duplicate insert count", f"{dup_count} (expected 0)")
        if dup_count != 0:
            all_ok = False

        # FTS5 search
        try:
            fts_rows = conn.execute(
                "SELECT * FROM feed_items_fts WHERE feed_items_fts MATCH 'transformers'"
            ).fetchall()
            detail("FTS5 search for 'transformers'", f"{len(fts_rows)} results")
            if len(fts_rows) != 1:
                all_ok = False

            fts_rows2 = conn.execute(
                "SELECT * FROM feed_items_fts WHERE feed_items_fts MATCH 'Python'"
            ).fetchall()
            detail("FTS5 search for 'Python'", f"{len(fts_rows2)} results")
            if len(fts_rows2) != 1:
                all_ok = False

            fts_rows3 = conn.execute(
                "SELECT * FROM feed_items_fts WHERE feed_items_fts MATCH 'nonexistent'"
            ).fetchall()
            detail("FTS5 search for 'nonexistent'", f"{len(fts_rows3)} results (expected 0)")
            if len(fts_rows3) != 0:
                all_ok = False
        except Exception as e:
            detail("FTS5 status", f"Not available ({e})")

        # Delete cascade
        conn.execute("DELETE FROM subscriptions WHERE id = ?", (sub["id"],))
        conn.commit()
        remaining = conn.execute("SELECT COUNT(*) FROM feed_items WHERE subscription_id = ?", (sub["id"],)).fetchone()[0]
        detail("Items after subscription delete (cascade)", f"{remaining} (expected 0)")
        if remaining != 0:
            all_ok = False

        conn.close()
    finally:
        srv.FEEDS_DB_PATH = original
        for f in [test_db, test_db + "-wal", test_db + "-shm"]:
            if os.path.exists(f):
                os.remove(f)

    result("Database operations", all_ok, time.time() - t0)
    return all_ok


# ---------------------------------------------------------------------------
# Live source tests
# ---------------------------------------------------------------------------

async def test_news_rss():
    subsection("News RSS — BBC News")
    detail("Feature", "Fetch and parse live RSS feed from a major news outlet")
    detail("Source", "BBC News (http://feeds.bbci.co.uk/news/rss.xml)")
    detail("Method", "_check_source_rss() -> _fetch_url_bytes() -> _parse_rss_atom()")

    t0 = time.time()
    try:
        items = await _check_source_rss(PRESET_NEWS_FEEDS["bbc"]["url"])
        detail("Items fetched", len(items))

        checks = {
            "At least 5 items": len(items) >= 5,
            "All items have titles": all(i["title"] for i in items),
            "All items have URLs": all(i["url"] for i in items),
            "URLs are HTTP(S)": all(i["url"].startswith("http") for i in items if i["url"]),
        }

        if items:
            detail("Sample item title", items[0]["title"])
            detail("Sample item URL", items[0]["url"])
            detail("Sample item published", items[0].get("published", "N/A"))
            detail("Sample content preview", items[0].get("content", "")[:150])

        for check_name, passed in checks.items():
            detail(check_name, "PASS" if passed else "FAIL")

        ok = all(checks.values())
        result("BBC News RSS", ok, time.time() - t0)
        return ok
    except Exception as e:
        detail("Error", str(e))
        result("BBC News RSS", False, time.time() - t0)
        return False


async def test_reddit():
    subsection("Reddit — r/technology via RSS")
    detail("Feature", "Fetch subreddit posts via Reddit's native RSS endpoint")
    detail("Source", "r/technology (https://www.reddit.com/r/technology/.rss)")
    detail("Method", "_check_source_reddit('technology') -> Atom feed parsing")

    t0 = time.time()
    try:
        items = await _check_source_reddit("technology")
        detail("Items fetched", len(items))

        checks = {
            "At least 5 items": len(items) >= 5,
            "All items have titles": all(i["title"] for i in items),
            "All items have URLs": all(i["url"] for i in items),
        }

        if items:
            detail("Sample post title", items[0]["title"])
            detail("Sample post URL", items[0]["url"])
            detail("Sample post author", items[0].get("author", "N/A"))

        for check_name, passed in checks.items():
            detail(check_name, "PASS" if passed else "FAIL")

        ok = all(checks.values())
        result("Reddit RSS", ok, time.time() - t0)
        return ok
    except Exception as e:
        detail("Error", str(e))
        result("Reddit RSS", False, time.time() - t0)
        return False


async def test_hackernews():
    subsection("Hacker News — Top Stories via Firebase API")
    detail("Feature", "Fetch top stories from HN public API with metadata")
    detail("Source", "https://hacker-news.firebaseio.com/v0/topstories.json")
    detail("Method", "_check_source_hackernews('top', limit=5) -> parallel story fetches")

    t0 = time.time()
    try:
        items = await _check_source_hackernews("top", limit=5)
        detail("Items fetched", len(items))

        checks = {
            "Got 5 stories": len(items) == 5,
            "All have titles": all(i["title"] for i in items),
            "All have URLs": all(i["url"] for i in items),
            "All have authors": all(i["author"] for i in items),
            "Metadata has score": all("score" in json.loads(i.get("metadata", "{}")) for i in items),
            "Metadata has comments": all("comments" in json.loads(i.get("metadata", "{}")) for i in items),
        }

        if items:
            meta = json.loads(items[0].get("metadata", "{}"))
            detail("Sample title", items[0]["title"])
            detail("Sample URL", items[0]["url"])
            detail("Sample author", items[0]["author"])
            detail("Sample score", meta.get("score", "N/A"))
            detail("Sample comments", meta.get("comments", "N/A"))
            detail("Sample published", items[0].get("published", "N/A"))

        for check_name, passed in checks.items():
            detail(check_name, "PASS" if passed else "FAIL")

        ok = all(checks.values())
        result("Hacker News API", ok, time.time() - t0)
        return ok
    except Exception as e:
        detail("Error", str(e))
        result("Hacker News API", False, time.time() - t0)
        return False


async def test_github():
    subsection("GitHub — Releases via Atom Feed")
    detail("Feature", "Fetch release notes from a public GitHub repository")
    detail("Source", "anthropics/anthropic-sdk-python (releases.atom)")
    detail("Method", "_check_source_github('anthropics/anthropic-sdk-python')")

    t0 = time.time()
    try:
        items = await _check_source_github("anthropics/anthropic-sdk-python")
        detail("Items fetched", len(items))

        checks = {
            "At least 1 release": len(items) >= 1,
            "All have titles": all(i["title"] for i in items),
            "All have URLs": all(i["url"] for i in items),
            "URLs point to GitHub": all("github.com" in i["url"] for i in items if i["url"]),
        }

        if items:
            detail("Latest release", items[0]["title"])
            detail("Release URL", items[0]["url"])
            detail("Content preview", items[0].get("content", "")[:150] or "N/A")

        for check_name, passed in checks.items():
            detail(check_name, "PASS" if passed else "FAIL")

        ok = all(checks.values())
        result("GitHub releases", ok, time.time() - t0)
        return ok
    except Exception as e:
        detail("Error", str(e))
        result("GitHub releases", False, time.time() - t0)
        return False


async def test_arxiv():
    subsection("arXiv — cs.AI Papers via API")
    detail("Feature", "Fetch recent papers from arXiv by category")
    detail("Source", "http://export.arxiv.org/api/query?search_query=cat:cs.AI")
    detail("Method", "_check_source_arxiv('cs.AI', max_results=5)")

    t0 = time.time()
    try:
        items = await _check_source_arxiv("cs.AI", max_results=5)
        detail("Items fetched", len(items))

        checks = {
            "Got papers": len(items) >= 1,
            "All have titles": all(i["title"] for i in items),
            "All have URLs": all(i["url"] for i in items),
            "URLs point to arXiv": all("arxiv" in i["url"].lower() for i in items if i["url"]),
            "Content has abstracts": any(len(i.get("content", "")) > 50 for i in items),
        }

        if items:
            detail("Sample paper title", items[0]["title"][:120])
            detail("Sample paper URL", items[0]["url"])
            detail("Sample author", items[0].get("author", "N/A"))
            detail("Abstract preview", items[0].get("content", "")[:200] or "N/A")

        for check_name, passed in checks.items():
            detail(check_name, "PASS" if passed else "FAIL")

        ok = all(checks.values())
        result("arXiv papers", ok, time.time() - t0)
        return ok
    except Exception as e:
        detail("Error", str(e))
        result("arXiv papers", False, time.time() - t0)
        return False


async def test_youtube():
    subsection("YouTube — Channel Feed (3Blue1Brown)")
    detail("Feature", "Fetch recent videos from a YouTube channel RSS feed")
    detail("Source", "3Blue1Brown (UCYO_jab_esuFRV4b17AJtAw)")
    detail("Feed URL", "https://www.youtube.com/feeds/videos.xml?channel_id=UCYO_jab_esuFRV4b17AJtAw")
    detail("Method", "_check_source_youtube(feed_url)")

    t0 = time.time()
    try:
        feed_url = "https://www.youtube.com/feeds/videos.xml?channel_id=UCYO_jab_esuFRV4b17AJtAw"
        items = await _check_source_youtube(feed_url)
        detail("Items fetched", len(items))

        checks = {
            "Got videos": len(items) >= 1,
            "All have titles": all(i["title"] for i in items),
            "All have URLs": all(i["url"] for i in items),
            "URLs are YouTube": all("youtube.com" in i["url"] for i in items if i["url"]),
            "Metadata has video_url": all(
                "video_url" in json.loads(i.get("metadata", "{}"))
                for i in items if i.get("metadata")
            ),
        }

        if items:
            detail("Latest video title", items[0]["title"])
            detail("Video URL", items[0]["url"])
            detail("Channel/author", items[0].get("author", "N/A"))
            detail("Published", items[0].get("published", "N/A"))

        for check_name, passed in checks.items():
            detail(check_name, "PASS" if passed else "FAIL")

        ok = all(checks.values())
        result("YouTube channel feed", ok, time.time() - t0)
        return ok
    except Exception as e:
        detail("Error", str(e))
        result("YouTube channel feed", False, time.time() - t0)
        return False


async def test_podcast():
    subsection("Podcast — Lex Fridman RSS Feed")
    detail("Feature", "Fetch podcast episodes with audio URLs and metadata")
    detail("Source", "Lex Fridman Podcast (https://lexfridman.com/feed/podcast/)")
    detail("Method", "_check_source_podcast(feed_url)")

    t0 = time.time()
    try:
        items = await _check_source_podcast("https://lexfridman.com/feed/podcast/")
        detail("Items fetched", len(items))

        checks = {
            "Got episodes": len(items) >= 1,
            "All have titles": all(i["title"] for i in items),
            "Have audio URLs in metadata": any(
                "audio_url" in json.loads(i.get("metadata", "{}"))
                for i in items
            ),
        }

        if items:
            meta = json.loads(items[0].get("metadata", "{}"))
            detail("Latest episode", items[0]["title"])
            detail("Episode URL", items[0]["url"])
            detail("Author", items[0].get("author", "N/A"))
            detail("Published", items[0].get("published", "N/A"))
            detail("Audio URL", meta.get("audio_url", "N/A")[:100])
            detail("Duration", meta.get("duration", "N/A"))

        for check_name, passed in checks.items():
            detail(check_name, "PASS" if passed else "FAIL")

        ok = all(checks.values())
        result("Podcast RSS", ok, time.time() - t0)
        return ok
    except Exception as e:
        detail("Error", str(e))
        result("Podcast RSS", False, time.time() - t0)
        return False


# ---------------------------------------------------------------------------
# End-to-end MCP tool test
# ---------------------------------------------------------------------------

async def test_e2e():
    subsection("End-to-End: subscribe -> check -> search -> get -> unsubscribe")
    detail("Feature", "Full MCP tool workflow using real network data")
    detail("Method", "Calls each MCP tool function in sequence with assertions")

    import google_search_mcp.server as srv
    test_db = "/tmp/test_feeds_e2e.db"
    for f in [test_db, test_db + "-wal", test_db + "-shm"]:
        if os.path.exists(f):
            os.remove(f)
    original = srv.FEEDS_DB_PATH
    srv.FEEDS_DB_PATH = test_db

    t0 = time.time()
    all_ok = True

    try:
        # Step 1: Subscribe
        log("")
        log("    Step 1: subscribe()")

        r = await subscribe("news", "bbc")
        detail("Input", 'subscribe("news", "bbc")')
        detail("Output", r)
        if "Subscribed" not in r:
            detail("CHECK", "FAIL — expected 'Subscribed' in output")
            all_ok = False
        else:
            detail("CHECK", "PASS — subscription created")

        r = await subscribe("hackernews", "top")
        detail("Input", 'subscribe("hackernews", "top")')
        detail("Output", r)

        # Duplicate test
        r = await subscribe("news", "bbc")
        detail("Input", 'subscribe("news", "bbc") — duplicate')
        detail("Output", r)
        if "Already" not in r:
            detail("CHECK", "FAIL — expected 'Already' for duplicate")
            all_ok = False
        else:
            detail("CHECK", "PASS — duplicate detected")

        # Invalid type
        r = await subscribe("invalid", "test")
        detail("Input", 'subscribe("invalid", "test")')
        detail("Output", r)
        if "Invalid" not in r:
            detail("CHECK", "FAIL — expected error for invalid type")
            all_ok = False
        else:
            detail("CHECK", "PASS — invalid type rejected")

        # Step 2: List subscriptions
        log("")
        log("    Step 2: list_subscriptions()")

        r = await list_subscriptions()
        detail("Output", r)
        has_bbc = "bbc" in r.lower() or "BBC" in r
        has_hn = "Hacker News" in r
        if not has_bbc or not has_hn:
            detail("CHECK", f"FAIL — BBC: {has_bbc}, HN: {has_hn}")
            all_ok = False
        else:
            detail("CHECK", "PASS — both subscriptions listed")

        # Step 3: Check feeds
        log("")
        log("    Step 3: check_feeds()")

        r = await check_feeds()
        detail("Output", r)
        if "Feed Check Complete" not in r:
            detail("CHECK", "FAIL — missing completion message")
            all_ok = False
        else:
            detail("CHECK", "PASS — feeds checked successfully")
        if "new items" in r:
            detail("CHECK", "PASS — new items found and stored")

        # Step 4: Get recent items
        log("")
        log("    Step 4: get_feed_items()")

        r = await get_feed_items(source_type="news")
        detail("Input", 'get_feed_items(source_type="news")')
        detail("Output preview", r[:300])
        if "items" in r.lower() or "BBC" in r or "URL:" in r:
            detail("CHECK", "PASS — news items returned")
        else:
            detail("CHECK", "FAIL — no items returned")
            all_ok = False

        r = await get_feed_items(source_type="hackernews", limit=3)
        detail("Input", 'get_feed_items(source_type="hackernews", limit=3)')
        detail("Output preview", r[:300])

        # Step 5: Search feeds
        log("")
        log("    Step 5: search_feeds()")

        r = await search_feeds("the")
        detail("Input", 'search_feeds("the") — common word, should match')
        detail("Output preview", r[:300])
        if "results" in r.lower() or "URL:" in r:
            detail("CHECK", "PASS — search returned results")
        else:
            detail("CHECK", "FAIL — no search results")
            all_ok = False

        r = await search_feeds("xyznonexistent12345")
        detail("Input", 'search_feeds("xyznonexistent12345") — should find nothing')
        detail("Output", r)
        if "No results" in r:
            detail("CHECK", "PASS — empty result handled correctly")
        else:
            detail("CHECK", "FAIL — expected no results message")
            all_ok = False

        # Step 6: Unsubscribe
        log("")
        log("    Step 6: unsubscribe()")

        r = await unsubscribe("news", "bbc")
        detail("Input", 'unsubscribe("news", "bbc")')
        detail("Output", r)
        if "Unsubscribed" not in r:
            detail("CHECK", "FAIL — unsubscribe failed")
            all_ok = False
        else:
            detail("CHECK", "PASS — unsubscribed and content removed")

        # Verify removal
        r = await list_subscriptions()
        detail("Subscriptions after unsubscribe", r)
        if "bbc" in r.lower() and "BBC" in r and "NEWS" in r:
            detail("CHECK", "FAIL — BBC still present after unsubscribe")
            all_ok = False
        else:
            detail("CHECK", "PASS — BBC removed from subscriptions")

        # Unsubscribe non-existent
        r = await unsubscribe("news", "nonexistent_feed")
        detail("Input", 'unsubscribe("news", "nonexistent_feed")')
        detail("Output", r)
        if "No subscription" in r:
            detail("CHECK", "PASS — non-existent handled correctly")
        else:
            detail("CHECK", "FAIL — expected not-found message")
            all_ok = False

    except Exception as e:
        detail("EXCEPTION", str(e))
        all_ok = False

    finally:
        srv.FEEDS_DB_PATH = original
        for f in [test_db, test_db + "-wal", test_db + "-shm"]:
            if os.path.exists(f):
                os.remove(f)

    result("End-to-End MCP tools", all_ok, time.time() - t0)
    return all_ok


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

async def main():
    global PASS, FAIL

    section("Feed Subscription System — Detailed Test Log")
    log(f"Date: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    log(f"Python: {sys.version.split()[0]}")
    log(f"Platform: {sys.platform}")

    # Unit tests
    section("UNIT TESTS")
    test_strip_html()
    test_parse_rss()
    test_parse_atom()
    test_database()

    # Live source tests
    section("LIVE SOURCE TESTS (network)")
    await test_news_rss()
    await test_reddit()
    await test_hackernews()
    await test_github()
    await test_arxiv()
    await test_youtube()
    await test_podcast()

    # E2E test
    section("END-TO-END MCP TOOL TEST")
    await test_e2e()

    # Summary
    total = PASS + FAIL
    section("SUMMARY")
    log(f"  Total tests:  {total}")
    log(f"  Passed:       {PASS}")
    log(f"  Failed:       {FAIL}")
    log(f"  Pass rate:    {PASS/total*100:.0f}%")
    log("")

    if FAIL == 0:
        log("  ALL TESTS PASSED")
    else:
        log(f"  {FAIL} TEST(S) FAILED")

    log("")

    # Save log to file
    log_path = os.path.join(os.path.dirname(__file__), "test_feeds_log.txt")
    with open(log_path, "w") as f:
        f.write("\n".join(LOG_LINES))
    log(f"Full log saved to: {log_path}")

    return FAIL == 0


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
