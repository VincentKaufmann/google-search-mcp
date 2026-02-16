# noapi-google-search-mcp v0.3.0 — Full Regression Test Report

**Date:** 2026-02-17 00:40:06
**Python:** 3.12.3
**Platform:** linux
**Tools:** 38
**Result:** 24/24 test groups PASSED, 120/120 checks PASSED (100%)

---

## Results

| # | Test | Checks | Time | Result |
|---|------|--------|------|--------|
| 1 | Tool count and registration | 17 | 0.00s | PASS |
| 2 | _strip_html — HTML tag removal | 5 | 0.00s | PASS |
| 3 | _parse_rss_atom — RSS 2.0 parsing | 7 | 0.00s | PASS |
| 4 | _parse_rss_atom — Atom parsing | 8 | 0.00s | PASS |
| 5 | SQLite + FTS5 database | 8 | 0.10s | PASS |
| 6 | News RSS — BBC News | 4 | 0.31s | PASS |
| 7 | Reddit — r/technology | 3 | 0.80s | PASS |
| 8 | Hacker News — Top Stories | 6 | 0.76s | PASS |
| 9 | GitHub — Releases | 4 | 0.57s | PASS |
| 10 | arXiv — cs.AI Papers | 5 | 0.30s | PASS |
| 11 | YouTube — 3Blue1Brown | 5 | 0.43s | PASS |
| 12 | Podcast — Lex Fridman | 3 | 2.20s | PASS |
| 13 | Full feed workflow | 13 | 1.36s | PASS |
| 14 | transcribe_local — local audio/video | 3 | 0.91s | PASS |
| 15 | convert_media — FFmpeg conversion | 2 | 0.27s | PASS |
| 16 | read_document — PDF/DOCX/text/HTML | 7 | 0.01s | PASS |
| 17 | fetch_emails — IMAP email pull | 5 | 0.27s | PASS |
| 18 | paste_text — dpaste.org pastebin | 2 | 0.87s | PASS |
| 19 | shorten_url — TinyURL | 1 | 0.08s | PASS |
| 20 | generate_qr — QR code generation | 2 | 0.08s | PASS |
| 21 | archive_webpage — Wayback Machine | 1 | 7.01s | PASS |
| 22 | wikipedia — article lookup | 4 | 2.21s | PASS |
| 23 | upload_to_s3 — MinIO/S3 upload | 2 | 0.00s | PASS |
| 24 | YouTube auto-transcription | 3 | 0.24s | PASS |
| | **Total** | **120/120** | **18.78s** | **24/24** |

---

```
ALL TESTS PASSED
```
