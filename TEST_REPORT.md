# Feed Subscription System v0.3.0 — Test Report

**Date:** 2026-02-16 22:34:26
**Python:** 3.12.3
**Platform:** linux
**Result:** 12/12 PASSED (100%)

---

## Test Categories

| Category | Tests | Passed | What's tested |
|----------|-------|--------|---------------|
| Unit Tests | 4 | 4 | HTML stripping, RSS parsing, Atom parsing, SQLite + FTS5 |
| Live Source Tests | 7 | 7 | BBC News, Reddit, Hacker News, GitHub, arXiv, YouTube, Podcast |
| End-to-End MCP Tools | 1 | 1 | Full subscribe -> check -> search -> get -> unsubscribe flow |

---

## Unit Tests

### 1. `_strip_html` — HTML tag removal

**What:** Verifies that HTML tags are correctly stripped from RSS feed content, leaving only clean text.

| Input | Expected Output | Actual Output | Result |
|-------|----------------|---------------|--------|
| `<p>Hello <b>world</b></p>` | `Hello world` | `Hello world` | PASS |
| *(empty string)* | *(empty string)* | *(empty string)* | PASS |
| `plain text` | `plain text` | `plain text` | PASS |
| `<a href='x'>link</a> and <em>emphasis</em>` | `link and emphasis` | `link and emphasis` | PASS |
| `<div><span>nested</span></div>` | `nested` | `nested` | PASS |

**Time:** 0.00s

---

### 2. `_parse_rss_atom` — RSS 2.0 feed parsing

**What:** Parses a synthetic RSS 2.0 XML document and verifies all fields are extracted correctly.

**Input:** RSS 2.0 XML with 2 items — one with plain text description, one with HTML-encoded `<p>` tags in description.

| Check | Result |
|-------|--------|
| Item count == 2 | PASS |
| First title == "Article One" | PASS |
| First URL == "https://example.com/1" | PASS |
| First content == "First article content" | PASS |
| First pubDate contains "Jan" | PASS |
| Second title == "Article Two" | PASS |
| HTML stripped from second content (no `<p>` tags) | PASS |

**Time:** 0.00s

---

### 3. `_parse_rss_atom` — Atom feed parsing

**What:** Parses a synthetic Atom XML document with namespaces, verifying `<entry>`, `<link rel="alternate">`, `<summary>`, `<content>`, `<published>`, `<updated>`, and `<author>` extraction.

**Input:** Atom XML with 2 entries — one with `<summary>` + `<published>`, one with `<content type="html">` + `<updated>` (no `<published>`).

| Check | Result |
|-------|--------|
| Item count == 2 | PASS |
| First title == "Entry One" | PASS |
| First URL from `rel=alternate` link == "https://example.com/a" | PASS |
| First author == "Alice" | PASS |
| First published contains "2024" | PASS |
| Second title == "Entry Two" | PASS |
| Second URL from plain `<link>` == "https://example.com/b" | PASS |
| HTML stripped from `<content>` (no `<p>` tags) | PASS |

**Time:** 0.00s

---

### 4. SQLite + FTS5 database operations

**What:** Tests the full database lifecycle — schema creation, subscription insert, item storage, duplicate detection, FTS5 full-text search, and cascade delete.

| Step | Input | Output | Result |
|------|-------|--------|--------|
| Create database | `_get_feeds_db()` | Created `/tmp/test_feeds_unit.db` | PASS |
| Verify tables | Query `sqlite_master` | Found: subscriptions, feed_items, feed_items_fts + internal FTS tables | PASS |
| Insert subscription | `(news, test_unit, "Unit Test Feed")` | id=1, name=Unit Test Feed | PASS |
| Store 3 items (1 has no URL) | 3 items, 1 missing URL | 2 new items stored (empty URL skipped) | PASS |
| Store same items again | Same 3 items | 0 new items (duplicates ignored via UNIQUE constraint) | PASS |
| FTS5 search: "transformers" | `MATCH 'transformers'` | 1 result (matched "Researchers discover new architecture for transformers") | PASS |
| FTS5 search: "Python" | `MATCH 'Python'` | 1 result (matched "Python 4.0 Released") | PASS |
| FTS5 search: "nonexistent" | `MATCH 'nonexistent'` | 0 results | PASS |
| Delete subscription (cascade) | `DELETE FROM subscriptions WHERE id=1` | 0 feed_items remaining (ON DELETE CASCADE worked) | PASS |

**Time:** 0.07s

---

## Live Source Tests (network)

### 5. News RSS — BBC News

**What:** Fetches the live BBC News RSS feed over the network, parses it, and validates the structure.

| Field | Value |
|-------|-------|
| **Feature tested** | Fetch and parse live RSS feed from a major news outlet |
| **Source URL** | `http://feeds.bbci.co.uk/news/rss.xml` |
| **Method** | `_check_source_rss()` -> `_fetch_url_bytes()` -> `_parse_rss_atom()` |
| **Items fetched** | 36 |
| **Sample title** | Government abandons plans to delay 30 council elections |
| **Sample URL** | https://www.bbc.com/news/articles/c70ne31d884o |
| **Sample published** | Mon, 16 Feb 2026 18:07:59 GMT |
| **Sample content** | All English elections will now go ahead as originally planned after Reform UK brought a legal challenge... |

| Check | Result |
|-------|--------|
| At least 5 items returned | PASS |
| All items have titles | PASS |
| All items have URLs | PASS |
| All URLs start with http(s) | PASS |

**Time:** 0.47s

---

### 6. Reddit — r/technology via RSS

**What:** Fetches Reddit's native Atom RSS feed for a subreddit, no authentication needed.

| Field | Value |
|-------|-------|
| **Feature tested** | Fetch subreddit posts via Reddit's native RSS endpoint |
| **Source URL** | `https://www.reddit.com/r/technology/.rss` |
| **Method** | `_check_source_reddit('technology')` -> Atom feed parsing |
| **Items fetched** | 25 |
| **Sample title** | Hi! We're 404 Media's Jason Koebler and Joseph Cox. AMA (us) about the tech ICE is using... |
| **Sample URL** | https://www.reddit.com/r/technology/comments/1qv9y8j/... |
| **Sample author** | /u/404mediaco |

| Check | Result |
|-------|--------|
| At least 5 items returned | PASS |
| All items have titles | PASS |
| All items have URLs | PASS |

**Time:** 0.92s

---

### 7. Hacker News — Top Stories via Firebase API

**What:** Fetches top stories from the HN public Firebase API, resolving individual story metadata in parallel.

| Field | Value |
|-------|-------|
| **Feature tested** | Fetch top stories from HN public API with score/comment metadata |
| **Source URL** | `https://hacker-news.firebaseio.com/v0/topstories.json` |
| **Method** | `_check_source_hackernews('top', limit=5)` -> parallel `asyncio.gather()` for each story |
| **Items fetched** | 5 |
| **Sample title** | 14-year-old Miles Wu folded origami pattern that holds 10k times its own weight |
| **Sample URL** | https://www.smithsonianmag.com/innovation/... |
| **Sample author** | bookofjoe |
| **Sample score** | 165 |
| **Sample comments** | 16 |
| **Sample published** | 2026-02-16T18:41:50+00:00 |

| Check | Result |
|-------|--------|
| Got exactly 5 stories | PASS |
| All have titles | PASS |
| All have URLs | PASS |
| All have authors | PASS |
| Metadata JSON contains "score" | PASS |
| Metadata JSON contains "comments" | PASS |

**Time:** 0.82s

---

### 8. GitHub — Releases via Atom Feed

**What:** Fetches release notes from a public GitHub repository's Atom feed.

| Field | Value |
|-------|-------|
| **Feature tested** | Fetch release notes from a public GitHub repository |
| **Source** | anthropics/anthropic-sdk-python |
| **Source URL** | `https://github.com/anthropics/anthropic-sdk-python/releases.atom` |
| **Method** | `_check_source_github('anthropics/anthropic-sdk-python')` |
| **Items fetched** | 10 |
| **Latest release** | v0.79.0 |
| **Release URL** | https://github.com/anthropics/anthropic-sdk-python/releases/tag/v0.79.0 |
| **Content preview** | 0.79.0 (2026-02-07) Full Changelog: v0.78.0...v0.79.0 Features api: enabling fast-mode in claude-opus-4-6... |

| Check | Result |
|-------|--------|
| At least 1 release | PASS |
| All have titles | PASS |
| All have URLs | PASS |
| All URLs point to github.com | PASS |

**Time:** 0.56s

---

### 9. arXiv — cs.AI Papers via API

**What:** Fetches recent papers from arXiv by category using their Atom API.

| Field | Value |
|-------|-------|
| **Feature tested** | Fetch recent papers from arXiv by category |
| **Source URL** | `http://export.arxiv.org/api/query?search_query=cat:cs.AI&max_results=5` |
| **Method** | `_check_source_arxiv('cs.AI', max_results=5)` |
| **Items fetched** | 5 |
| **Sample title** | Semantic Chunking and the Entropy of Natural Language |
| **Sample URL** | https://arxiv.org/abs/2602.13194v1 |
| **Sample author** | Weishun Zhong |
| **Abstract preview** | The entropy rate of printed English is famously estimated to be about one bit per character, a benchmark that modern large language models (LLMs) have only recently approached... |

| Check | Result |
|-------|--------|
| Got papers | PASS |
| All have titles | PASS |
| All have URLs | PASS |
| All URLs contain "arxiv" | PASS |
| At least one item has abstract > 50 chars | PASS |

**Time:** 0.44s

---

### 10. YouTube — Channel Feed (3Blue1Brown)

**What:** Fetches recent videos from a YouTube channel's RSS feed and extracts video URLs for transcription.

| Field | Value |
|-------|-------|
| **Feature tested** | Fetch recent videos from a YouTube channel RSS feed |
| **Source** | 3Blue1Brown (UCYO_jab_esuFRV4b17AJtAw) |
| **Feed URL** | `https://www.youtube.com/feeds/videos.xml?channel_id=UCYO_jab_esuFRV4b17AJtAw` |
| **Method** | `_check_source_youtube(feed_url)` |
| **Items fetched** | 15 |
| **Latest video** | Solution to the ladybug clock puzzle |
| **Video URL** | https://www.youtube.com/shorts/7gG91SZwBoE |
| **Channel/author** | 3Blue1Brown |
| **Published** | 2026-02-16T14:08:37+00:00 |

| Check | Result |
|-------|--------|
| Got videos | PASS |
| All have titles | PASS |
| All have URLs | PASS |
| All URLs contain "youtube.com" | PASS |
| Metadata JSON contains "video_url" (for transcription) | PASS |

**Time:** 0.26s

---

### 11. Podcast — Lex Fridman RSS Feed

**What:** Fetches podcast episodes including audio enclosure URLs and iTunes metadata.

| Field | Value |
|-------|-------|
| **Feature tested** | Fetch podcast episodes with audio URLs and metadata |
| **Source** | Lex Fridman Podcast |
| **Feed URL** | `https://lexfridman.com/feed/podcast/` |
| **Method** | `_check_source_podcast(feed_url)` |
| **Items fetched** | 492 |
| **Latest episode** | #491 -- OpenClaw: The Viral AI Agent that Broke the Internet -- Peter Steinberger |
| **Episode URL** | https://lexfridman.com/peter-steinberger/ |
| **Author** | Lex Fridman |
| **Published** | Thu, 12 Feb 2026 03:10:39 +0000 |
| **Audio URL** | https://media.blubrry.com/takeituneasy/ins.blubrry.com/takeituneasy/lex_ai_peter_steinberger.mp3 |

| Check | Result |
|-------|--------|
| Got episodes | PASS |
| All have titles | PASS |
| At least one has audio_url in metadata | PASS |

**Time:** 2.36s

---

## End-to-End MCP Tool Test

### 12. Full workflow: subscribe -> check -> search -> get -> unsubscribe

**What:** Tests all 6 MCP tools in sequence with real network data, using an isolated test database.

#### Step 1: `subscribe()`

| Input | Output | Check |
|-------|--------|-------|
| `subscribe("news", "bbc")` | Subscribed to BBC News (news). Run check_feeds to fetch content. | PASS -- subscription created |
| `subscribe("hackernews", "top")` | Subscribed to Hacker News (top) (hackernews). Run check_feeds to fetch content. | PASS |
| `subscribe("news", "bbc")` *(duplicate)* | Already subscribed to BBC News (news). | PASS -- duplicate detected |
| `subscribe("invalid", "test")` | Invalid source type 'invalid'. Must be one of: news, reddit, hackernews, github, arxiv, youtube, podcast, twitter | PASS -- invalid type rejected |

#### Step 2: `list_subscriptions()`

| Input | Output | Check |
|-------|--------|-------|
| `list_subscriptions()` | Active Subscriptions (2 total) -- HACKERNEWS: Hacker News (top) 0 items, never checked -- NEWS: BBC News 0 items, never checked | PASS -- both subscriptions listed |

#### Step 3: `check_feeds()`

| Input | Output | Check |
|-------|--------|-------|
| `check_feeds()` | Feed Check Complete -- BBC News: 36 new items -- Hacker News (top): 29 new items -- Total: 65 new items across 2 sources | PASS -- feeds checked, 65 items stored |

#### Step 4: `get_feed_items()`

| Input | Output (preview) | Check |
|-------|--------|-------|
| `get_feed_items(source_type="news")` | Recent Feed Items (20 items) -- 1. [news/BBC News] BBC News app -- Published: Wed, 30 Apr 2025... -- URL: https://www.bbc.co.uk/news/10628994... | PASS -- news items returned |
| `get_feed_items(source_type="hackernews", limit=3)` | Recent Feed Items (3 items) -- 1. [hackernews/Hacker News (top)] Study: Self-generated Agent Skills are useless -- URL: https://arxiv.org/abs/2602.12670 | PASS |

#### Step 5: `search_feeds()`

| Input | Output (preview) | Check |
|-------|--------|-------|
| `search_feeds("the")` | Feed Search: "the" (20 results) -- 1. [news/BBC News] Will the US Supreme Court stand up to Trump?... | PASS -- FTS5 search returned results |
| `search_feeds("xyznonexistent12345")` | No results found for: "xyznonexistent12345" | PASS -- empty result handled correctly |

#### Step 6: `unsubscribe()`

| Input | Output | Check |
|-------|--------|-------|
| `unsubscribe("news", "bbc")` | Unsubscribed from BBC News. Stored content removed. | PASS -- unsubscribed and content removed |
| `list_subscriptions()` after unsubscribe | Active Subscriptions (1 total) -- HACKERNEWS: Hacker News (top) 29 items | PASS -- BBC removed, HN items preserved |
| `unsubscribe("news", "nonexistent_feed")` | No subscription found for 'nonexistent_feed'. | PASS -- non-existent handled correctly |

**Time:** 1.54s

---

## Summary

```
Total tests:  12
Passed:       12
Failed:       0
Pass rate:    100%

ALL TESTS PASSED
```

| Test | Time | Result |
|------|------|--------|
| _strip_html (5 cases) | 0.00s | PASS |
| RSS 2.0 parsing (7 checks) | 0.00s | PASS |
| Atom parsing (8 checks) | 0.00s | PASS |
| SQLite + FTS5 (9 operations) | 0.07s | PASS |
| BBC News RSS (4 checks) | 0.47s | PASS |
| Reddit r/technology (3 checks) | 0.92s | PASS |
| Hacker News API (6 checks) | 0.82s | PASS |
| GitHub releases (4 checks) | 0.56s | PASS |
| arXiv cs.AI papers (5 checks) | 0.44s | PASS |
| YouTube 3Blue1Brown (5 checks) | 0.26s | PASS |
| Lex Fridman Podcast (3 checks) | 2.36s | PASS |
| E2E MCP tool flow (17 checks) | 1.54s | PASS |
| **Total** | **7.44s** | **12/12** |
