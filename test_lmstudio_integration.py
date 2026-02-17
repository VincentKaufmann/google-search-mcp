#!/usr/bin/env python3
"""
LM Studio + MCP Integration Test
=================================
Tests MCP tools through the LM Studio API with gpt-oss-120b.

For each tool we:
  1. Send a natural-language prompt to the LLM with tool definitions
  2. Verify the LLM picks the correct tool and arguments
  3. Log full input/output for every call

Saves detailed results to test_lmstudio_results.md
"""

import json
import sys
import time
import urllib.request
import urllib.error
from datetime import datetime

# ── Config ────────────────────────────────────────────────────────────────────
LMSTUDIO_URL = "http://localhost:1234/v1/chat/completions"
MODEL = "openai/gpt-oss-120b"
TIMEOUT = 120
LOG_FILE = "/home/xentureon/google-search-mcp/test_lmstudio_results.md"

# ── Tool definitions ─────────────────────────────────────────────────────────
TOOL_DEFS = {
    "google_search": {
        "description": "Search Google for web results",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search query"},
                "num_results": {"type": "integer", "description": "Number of results (1-10)"},
            },
            "required": ["query"],
        },
    },
    "google_news": {
        "description": "Search Google News for recent articles",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "News search query"},
                "num_results": {"type": "integer", "description": "Number of results"},
            },
            "required": ["query"],
        },
    },
    "google_scholar": {
        "description": "Search Google Scholar for academic papers",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Academic search query"},
                "num_results": {"type": "integer", "description": "Number of results"},
            },
            "required": ["query"],
        },
    },
    "google_images": {
        "description": "Search Google Images",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Image search query"},
                "num_results": {"type": "integer", "description": "Number of results"},
            },
            "required": ["query"],
        },
    },
    "google_weather": {
        "description": "Get weather forecast for a location",
        "parameters": {
            "type": "object",
            "properties": {
                "location": {"type": "string", "description": "City or location"},
            },
            "required": ["location"],
        },
    },
    "google_finance": {
        "description": "Get stock price and financial data",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Stock ticker or company name"},
            },
            "required": ["query"],
        },
    },
    "google_translate": {
        "description": "Translate text between languages",
        "parameters": {
            "type": "object",
            "properties": {
                "text": {"type": "string", "description": "Text to translate"},
                "to_language": {"type": "string", "description": "Target language"},
            },
            "required": ["text", "to_language"],
        },
    },
    "google_shopping": {
        "description": "Search Google Shopping for products with prices",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Product search query"},
                "num_results": {"type": "integer", "description": "Number of results"},
            },
            "required": ["query"],
        },
    },
    "google_flights": {
        "description": "Search for flights between cities",
        "parameters": {
            "type": "object",
            "properties": {
                "origin": {"type": "string", "description": "Departure city or airport"},
                "destination": {"type": "string", "description": "Arrival city or airport"},
            },
            "required": ["origin", "destination"],
        },
    },
    "google_hotels": {
        "description": "Search for hotels in a location",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Hotel search query with location"},
                "num_results": {"type": "integer", "description": "Number of results"},
            },
            "required": ["query"],
        },
    },
    "google_maps": {
        "description": "Search for places on Google Maps and return results with a map screenshot",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Place search query"},
                "num_results": {"type": "integer", "description": "Number of results"},
            },
            "required": ["query"],
        },
    },
    "google_maps_directions": {
        "description": "Get directions between two locations with a route map screenshot",
        "parameters": {
            "type": "object",
            "properties": {
                "origin": {"type": "string", "description": "Starting location"},
                "destination": {"type": "string", "description": "Ending location"},
            },
            "required": ["origin", "destination"],
        },
    },
    "google_trends": {
        "description": "Get Google Trends data for a topic",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Topic to check trends for"},
            },
            "required": ["query"],
        },
    },
    "google_books": {
        "description": "Search for books on Google Books",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Book search query"},
                "num_results": {"type": "integer", "description": "Number of results"},
            },
            "required": ["query"],
        },
    },
    "visit_page": {
        "description": "Fetch and read the content of a web page",
        "parameters": {
            "type": "object",
            "properties": {
                "url": {"type": "string", "description": "URL to visit"},
            },
            "required": ["url"],
        },
    },
    "google_lens": {
        "description": "Reverse image search - identify objects, products, landmarks",
        "parameters": {
            "type": "object",
            "properties": {
                "image_source": {"type": "string", "description": "Image URL or file path"},
            },
            "required": ["image_source"],
        },
    },
    "ocr_image": {
        "description": "Extract text from an image using local OCR",
        "parameters": {
            "type": "object",
            "properties": {
                "image_source": {"type": "string", "description": "Path to image file"},
            },
            "required": ["image_source"],
        },
    },
    "transcribe_video": {
        "description": "Download and transcribe a NEW video that has not been transcribed yet. Only use this for first-time transcription, NOT for searching existing transcripts.",
        "parameters": {
            "type": "object",
            "properties": {
                "url": {"type": "string", "description": "YouTube video URL"},
            },
            "required": ["url"],
        },
    },
    "search_transcript": {
        "description": "Search inside an ALREADY transcribed video for a keyword or topic. Use this when the user says 'search the transcript' or 'find in the video'. Do NOT use transcribe_video for this.",
        "parameters": {
            "type": "object",
            "properties": {
                "url": {"type": "string", "description": "YouTube video URL"},
                "query": {"type": "string", "description": "Keyword or phrase to search for"},
            },
            "required": ["url", "query"],
        },
    },
    "extract_video_clip": {
        "description": "Extract a video clip by specifying start and end times in seconds",
        "parameters": {
            "type": "object",
            "properties": {
                "url": {"type": "string", "description": "YouTube URL or local video"},
                "start_seconds": {"type": "number", "description": "Start time in seconds"},
                "end_seconds": {"type": "number", "description": "End time in seconds"},
            },
            "required": ["url", "start_seconds", "end_seconds"],
        },
    },
    "subscribe": {
        "description": "Subscribe to or follow any content feed source. Use this when the user says 'subscribe', 'follow', 'monitor', or 'watch'. Supported types: news, reddit, hackernews, github, arxiv, youtube, podcast, twitter.",
        "parameters": {
            "type": "object",
            "properties": {
                "source_type": {"type": "string", "description": "Source type: news, reddit, hackernews, github, arxiv, youtube, podcast, twitter"},
                "identifier": {"type": "string", "description": "Source identifier"},
            },
            "required": ["source_type", "identifier"],
        },
    },
    "unsubscribe": {
        "description": "Remove a feed subscription",
        "parameters": {
            "type": "object",
            "properties": {
                "source_type": {"type": "string", "description": "Source type"},
                "identifier": {"type": "string", "description": "Source identifier"},
            },
            "required": ["source_type", "identifier"],
        },
    },
    "list_subscriptions": {
        "description": "List all active feed subscriptions",
        "parameters": {
            "type": "object",
            "properties": {},
        },
    },
    "check_feeds": {
        "description": "Fetch new content from all subscribed feeds",
        "parameters": {
            "type": "object",
            "properties": {
                "source_type": {"type": "string", "description": "Limit to one source type"},
            },
        },
    },
    "search_feeds": {
        "description": "Full-text search across stored feed content",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search query"},
                "limit": {"type": "integer", "description": "Max results"},
            },
            "required": ["query"],
        },
    },
    "get_feed_items": {
        "description": "Browse recent items from feeds, optionally filtered by source or type",
        "parameters": {
            "type": "object",
            "properties": {
                "source": {"type": "string", "description": "Filter by source name"},
                "source_type": {"type": "string", "description": "Filter by type"},
                "limit": {"type": "integer", "description": "Max items"},
            },
        },
    },
    "transcribe_local": {
        "description": "Transcribe a local audio or video file using Whisper",
        "parameters": {
            "type": "object",
            "properties": {
                "file_path": {"type": "string", "description": "Path to audio/video file"},
            },
            "required": ["file_path"],
        },
    },
    "convert_media": {
        "description": "Convert between audio/video formats using FFmpeg",
        "parameters": {
            "type": "object",
            "properties": {
                "input_path": {"type": "string", "description": "Input file path"},
                "output_format": {"type": "string", "description": "Output format (mp3, mp4, wav, gif, etc.)"},
            },
            "required": ["input_path", "output_format"],
        },
    },
    "read_document": {
        "description": "Extract text from PDF, DOCX, HTML, and other document formats",
        "parameters": {
            "type": "object",
            "properties": {
                "file_path": {"type": "string", "description": "Path to document"},
            },
            "required": ["file_path"],
        },
    },
    "fetch_emails": {
        "description": "Pull emails via IMAP from Gmail, Outlook, Yahoo, or any IMAP server",
        "parameters": {
            "type": "object",
            "properties": {
                "email": {"type": "string", "description": "Email address"},
                "password": {"type": "string", "description": "Email password or app password"},
            },
            "required": ["email", "password"],
        },
    },
    "paste_text": {
        "description": "Post text to a pastebin service and get a shareable link",
        "parameters": {
            "type": "object",
            "properties": {
                "content": {"type": "string", "description": "Text content to paste"},
                "title": {"type": "string", "description": "Optional title"},
            },
            "required": ["content"],
        },
    },
    "shorten_url": {
        "description": "Shorten a URL using TinyURL",
        "parameters": {
            "type": "object",
            "properties": {
                "url": {"type": "string", "description": "URL to shorten"},
            },
            "required": ["url"],
        },
    },
    "generate_qr": {
        "description": "Generate a QR code image for any data (URL, text, Wi-Fi, etc.)",
        "parameters": {
            "type": "object",
            "properties": {
                "data": {"type": "string", "description": "Data to encode in the QR code"},
            },
            "required": ["data"],
        },
    },
    "archive_webpage": {
        "description": "Archive a webpage on the Wayback Machine",
        "parameters": {
            "type": "object",
            "properties": {
                "url": {"type": "string", "description": "URL to archive"},
            },
            "required": ["url"],
        },
    },
    "wikipedia": {
        "description": "Look up a Wikipedia article",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Article title or topic"},
            },
            "required": ["query"],
        },
    },
    "upload_to_s3": {
        "description": "Upload a file to cloud storage. Use this when the user says 'upload to S3', 'upload to MinIO', 'upload to bucket', or 'store in S3'. Works with MinIO, AWS S3, DigitalOcean Spaces, Cloudflare R2, Backblaze B2.",
        "parameters": {
            "type": "object",
            "properties": {
                "file_path": {"type": "string", "description": "Path to file"},
                "bucket": {"type": "string", "description": "Bucket name"},
            },
            "required": ["file_path", "bucket"],
        },
    },
    "list_images": {
        "description": "List image files in a directory",
        "parameters": {
            "type": "object",
            "properties": {
                "directory": {"type": "string", "description": "Folder to scan"},
            },
        },
    },
}

# ── Test cases: (prompt, expected_tool, arg_checks, category) ────────────────
TEST_CASES = [
    # --- Google Search & Web ---
    ("Search Google for best budget GPU for LLM inference", "google_search", {"query": "gpu"}, "Google Search"),
    ("Find recent news about OpenAI", "google_news", {"query": "openai"}, "Google News"),
    ("Find academic papers about attention mechanisms in transformers", "google_scholar", {"query": "attention"}, "Google Scholar"),
    ("Show me images of the Northern Lights", "google_images", {"query": "northern"}, "Google Images"),
    ("What is the weather in Tokyo right now?", "google_weather", {"location": "tokyo"}, "Google Weather"),
    ("What is Apple stock price? Use google_finance to look it up.", "google_finance", {"query": "apple"}, "Google Finance"),
    ("Translate 'good morning' to German", "google_translate", {"text": "good morning"}, "Google Translate"),
    ("Find me the cheapest RTX 4090 for sale", "google_shopping", {"query": "4090"}, "Google Shopping"),
    ("Search for flights from New York to London", "google_flights", {"origin": "new york"}, "Google Flights"),
    ("Search for hotels in Paris", "google_hotels", {"query": "paris"}, "Google Hotels"),
    ("Use google_maps to find pizza restaurants near Times Square in New York", "google_maps", {"query": "pizza"}, "Google Maps"),
    ("Get driving directions from Berlin to Munich using google_maps_directions", "google_maps_directions", {}, "Google Maps Directions"),
    ("Show me Google Trends for artificial intelligence", "google_trends", {"query": "artificial intelligence"}, "Google Trends"),
    ("Find books about machine learning", "google_books", {"query": "machine learning"}, "Google Books"),
    ("Read this web page for me: https://example.com", "visit_page", {"url": "example.com"}, "Visit Page"),

    # --- Vision & OCR ---
    ("Use Google Lens reverse image search on this image: /tmp/test.jpg", "google_lens", {}, "Google Lens"),
    ("Extract text from this screenshot using OCR: /tmp/screenshot.png", "ocr_image", {"image_source": "screenshot.png"}, "OCR Image"),

    # --- Video Intelligence ---
    ("Transcribe this YouTube video: https://youtube.com/watch?v=abc123", "transcribe_video", {"url": "youtube"}, "Transcribe Video"),
    ("Search the transcript of https://youtube.com/watch?v=abc123 for the word 'attention'", "search_transcript", {"query": "attention"}, "Search Transcript"),
    ("Extract a clip from https://youtube.com/watch?v=abc123 from 60 to 120 seconds", "extract_video_clip", {"url": "youtube"}, "Extract Video Clip"),

    # --- Feed Subscriptions ---
    ("Subscribe to BBC News feed", "subscribe", {"source_type": "news", "identifier": "bbc"}, "Subscribe (News)"),
    ("Subscribe to the subreddit r/LocalLLaMA", "subscribe", {"source_type": "reddit", "identifier": "localllama"}, "Subscribe (Reddit)"),
    ("Subscribe to Hacker News top stories", "subscribe", {"source_type": "hackernews"}, "Subscribe (HN)"),
    ("Subscribe to the YouTube channel @3Blue1Brown", "subscribe", {"source_type": "youtube", "identifier": "3blue1brown"}, "Subscribe (YouTube)"),
    ("Watch the GitHub repo anthropics/claude-code for new releases", "subscribe", {"source_type": "github", "identifier": "anthropics"}, "Subscribe (GitHub)"),
    ("Subscribe to the machine learning arXiv category", "subscribe", {"source_type": "arxiv"}, "Subscribe (arXiv)"),
    ("Follow @elonmusk on Twitter", "subscribe", {"source_type": "twitter", "identifier": "elon"}, "Subscribe (Twitter)"),
    ("Show me all my feed subscriptions", "list_subscriptions", {}, "List Subscriptions"),
    ("Check all my feeds for new content", "check_feeds", {}, "Check Feeds"),
    ("Search my feeds for transformer architecture", "search_feeds", {"query": "transformer"}, "Search Feeds"),
    ("Show me the latest items from my Reddit feeds", "get_feed_items", {"source_type": "reddit"}, "Get Feed Items"),
    ("Unsubscribe from BBC News", "unsubscribe", {"source_type": "news"}, "Unsubscribe"),

    # --- Local File Processing ---
    ("Transcribe this local recording: ~/meeting.mp3", "transcribe_local", {"file_path": "meeting"}, "Transcribe Local"),
    ("Convert video.mp4 to mp3 format", "convert_media", {"output_format": "mp3"}, "Convert Media"),
    ("Read this PDF document: ~/report.pdf", "read_document", {"file_path": "report"}, "Read Document"),

    # --- Email ---
    ("Check my email at user@gmail.com with password abc123", "fetch_emails", {"email": "gmail"}, "Fetch Emails"),

    # --- Web Utilities ---
    ("Shorten this URL: https://www.example.com/very/long/path", "shorten_url", {"url": "example.com"}, "Shorten URL"),
    ("Look up quantum computing on Wikipedia", "wikipedia", {"query": "quantum"}, "Wikipedia"),
    ("Post this text to a pastebin: Hello World test paste", "paste_text", {"content": "hello"}, "Paste Text"),
    ("Generate a QR code for https://mysite.com", "generate_qr", {"data": "mysite"}, "Generate QR"),
    ("Archive this webpage on the Wayback Machine: https://example.com", "archive_webpage", {"url": "example.com"}, "Archive Webpage"),

    # --- Cloud Storage ---
    ("Upload report.pdf to my S3 bucket called my-docs", "upload_to_s3", {"bucket": "my-docs"}, "Upload to S3"),
]


SYSTEM_PROMPT = (
    "You are a tool-calling assistant. You MUST call one of the provided tools "
    "for every user request. NEVER respond with text — always pick the most "
    "appropriate tool and call it with the correct arguments. "
    "If the user asks to 'search a transcript' or 'find in transcript', use "
    "search_transcript, NOT transcribe_video. "
    "If the user asks to 'follow' or 'subscribe' to anything, use subscribe. "
    "If the user asks to 'upload' a file, use upload_to_s3."
)


def llm_call(prompt: str, tools: list[dict]) -> dict:
    """Send a prompt to LM Studio with tool definitions."""
    payload = json.dumps({
        "model": MODEL,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ],
        "max_tokens": 300,
        "temperature": 0.0,
        "tool_choice": "required",
        "tools": tools,
    }).encode()

    req = urllib.request.Request(
        LMSTUDIO_URL,
        data=payload,
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
        return json.loads(resp.read())


def build_tools_list() -> list[dict]:
    """Build OpenAI-style tools array from all definitions."""
    return [
        {
            "type": "function",
            "function": {
                "name": name,
                "description": TOOL_DEFS[name]["description"],
                "parameters": TOOL_DEFS[name]["parameters"],
            },
        }
        for name in TOOL_DEFS
    ]


def run_tests():
    results = []
    passed = 0
    failed = 0
    errors = 0
    start_time = time.time()
    tools = build_tools_list()
    full_log_lines = []  # raw input/output log

    header = (
        f"{'='*70}\n"
        f"LM Studio Integration Test - gpt-oss-120b + MCP (38 tools)\n"
        f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
        f"Tests: {len(TEST_CASES)} | Tools registered: {len(TOOL_DEFS)}\n"
        f"{'='*70}\n"
    )
    print(header)
    full_log_lines.append(header)

    for i, (prompt, expected_tool, arg_checks, category) in enumerate(TEST_CASES, 1):
        print(f"[{i:02d}/{len(TEST_CASES)}] [{category}] {prompt[:60]}...")
        sys.stdout.flush()

        result = {
            "num": i,
            "category": category,
            "prompt": prompt,
            "expected_tool": expected_tool,
            "status": "FAIL",
            "tool_called": None,
            "args": None,
            "llm_content": None,
            "llm_reasoning": None,
            "tool_correct": False,
            "args_correct": False,
            "error": None,
            "latency_s": 0,
            "raw_response": None,
        }

        try:
            t0 = time.time()
            resp = llm_call(prompt, tools)
            result["latency_s"] = round(time.time() - t0, 1)
            result["raw_response"] = resp

            choice = resp["choices"][0]["message"]
            result["llm_content"] = choice.get("content", "")
            result["llm_reasoning"] = choice.get("reasoning", "")
            tool_calls = choice.get("tool_calls", [])

            if not tool_calls:
                result["error"] = f"No tool called. LLM said: {choice.get('content', '')[:200]}"
                failed += 1
                line = f"       FAIL - No tool called\n"
            else:
                tc = tool_calls[0]
                called_name = tc["function"]["name"]
                called_args_raw = tc["function"].get("arguments", "{}")
                try:
                    called_args = json.loads(called_args_raw) if isinstance(called_args_raw, str) else called_args_raw
                except json.JSONDecodeError:
                    called_args = {}

                result["tool_called"] = called_name
                result["args"] = called_args
                result["tool_correct"] = (called_name == expected_tool)

                args_ok = True
                for key, expected_substr in arg_checks.items():
                    val = str(called_args.get(key, "")).lower()
                    if expected_substr.lower() not in val:
                        args_ok = False
                        break
                result["args_correct"] = args_ok

                if result["tool_correct"] and result["args_correct"]:
                    result["status"] = "PASS"
                    passed += 1
                    line = f"       PASS ({result['latency_s']}s) -> {called_name}({json.dumps(called_args)[:80]})\n"
                elif result["tool_correct"]:
                    result["status"] = "PARTIAL"
                    failed += 1
                    line = f"       PARTIAL - right tool, wrong args: {called_args}\n"
                else:
                    result["status"] = "FAIL"
                    failed += 1
                    line = f"       FAIL - expected {expected_tool}, got {called_name}\n"

        except Exception as e:
            result["error"] = str(e)
            result["status"] = "ERROR"
            errors += 1
            line = f"       ERROR - {e}\n"

        print(line, end="")

        # Build detailed log entry
        log_entry = (
            f"\n{'─'*70}\n"
            f"TEST {i:02d}: {category} [{result['status']}]\n"
            f"{'─'*70}\n"
            f"INPUT PROMPT:\n  \"{prompt}\"\n\n"
            f"EXPECTED TOOL: {expected_tool}\n"
            f"EXPECTED ARGS CHECK: {arg_checks}\n\n"
        )
        if result["llm_reasoning"]:
            log_entry += f"LLM REASONING:\n  {result['llm_reasoning'][:300]}\n\n"
        if result["tool_called"]:
            log_entry += f"TOOL CALLED: {result['tool_called']}\n"
            log_entry += f"ARGUMENTS: {json.dumps(result['args'], indent=2)}\n\n"
        else:
            log_entry += f"TOOL CALLED: (none)\n"
            if result["llm_content"]:
                log_entry += f"LLM RESPONSE: {result['llm_content'][:300]}\n\n"
        log_entry += f"TOOL CORRECT: {result['tool_correct']}\n"
        log_entry += f"ARGS CORRECT: {result['args_correct']}\n"
        log_entry += f"LATENCY: {result['latency_s']}s\n"
        if result["error"]:
            log_entry += f"ERROR: {result['error']}\n"
        log_entry += f"STATUS: {result['status']}\n"

        full_log_lines.append(log_entry)
        results.append(result)
        sys.stdout.flush()

    total_time = round(time.time() - start_time, 1)
    avg_latency = round(sum(r["latency_s"] for r in results) / len(results), 1)

    # ── Summary ──────────────────────────────────────────────────────────
    summary = (
        f"\n{'='*70}\n"
        f"RESULTS: {passed}/{len(TEST_CASES)} passed, {failed} failed, {errors} errors\n"
        f"Total time: {total_time}s | Avg latency: {avg_latency}s/call\n"
        f"{'='*70}\n"
    )
    print(summary)
    full_log_lines.append(summary)

    # ── Write markdown report ────────────────────────────────────────────
    with open(LOG_FILE, "w") as f:
        f.write("# LM Studio Integration Test Report\n\n")
        f.write(f"**Date:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
        f.write(f"**Model:** {MODEL}\n\n")
        f.write(f"**MCP Server:** noapi-google-search-mcp v0.3.0 (38 tools)\n\n")
        f.write(f"**Result:** {passed}/{len(TEST_CASES)} passed, {failed} failed, {errors} errors\n\n")
        f.write(f"**Total time:** {total_time}s | **Avg latency:** {avg_latency}s/call\n\n")
        f.write("---\n\n")

        # Summary table
        f.write("## Summary Table\n\n")
        f.write("| # | Category | Prompt | Expected | Called | Args OK | Status | Latency |\n")
        f.write("|---|----------|--------|----------|--------|---------|--------|---------|\n")
        for r in results:
            prompt_short = r["prompt"][:40] + "..." if len(r["prompt"]) > 40 else r["prompt"]
            called = r["tool_called"] or "(none)"
            args_ok = "yes" if r["args_correct"] else "no"
            f.write(f"| {r['num']} | {r['category']} | {prompt_short} | `{r['expected_tool']}` | `{called}` | {args_ok} | {r['status']} | {r['latency_s']}s |\n")

        # Category breakdown
        f.write("\n---\n\n## Results by Category\n\n")
        categories = {}
        for r in results:
            cat = r["category"]
            if cat not in categories:
                categories[cat] = {"pass": 0, "fail": 0, "total": 0}
            categories[cat]["total"] += 1
            if r["status"] == "PASS":
                categories[cat]["pass"] += 1
            else:
                categories[cat]["fail"] += 1

        f.write("| Category | Passed | Failed | Total |\n")
        f.write("|----------|--------|--------|-------|\n")
        for cat, counts in categories.items():
            status = "PASS" if counts["fail"] == 0 else "FAIL"
            f.write(f"| {cat} | {counts['pass']} | {counts['fail']} | {counts['total']} |\n")

        # Detailed input/output for every test
        f.write("\n---\n\n## Detailed Input/Output Log\n\n")
        for r in results:
            icon = "PASS" if r["status"] == "PASS" else ("PARTIAL" if r["status"] == "PARTIAL" else "FAIL")
            f.write(f"### Test {r['num']:02d}: {r['category']} - {icon}\n\n")
            f.write(f"**User prompt:**\n```\n{r['prompt']}\n```\n\n")
            f.write(f"**Expected tool:** `{r['expected_tool']}`\n\n")
            if r["llm_reasoning"]:
                f.write(f"**LLM reasoning:**\n```\n{r['llm_reasoning'][:500]}\n```\n\n")
            if r["tool_called"]:
                f.write(f"**Tool called:** `{r['tool_called']}`\n\n")
                f.write(f"**Arguments:**\n```json\n{json.dumps(r['args'], indent=2)}\n```\n\n")
            else:
                f.write(f"**Tool called:** (none)\n\n")
                if r["llm_content"]:
                    f.write(f"**LLM text response:**\n```\n{r['llm_content'][:500]}\n```\n\n")
            f.write(f"**Tool correct:** {r['tool_correct']} | **Args correct:** {r['args_correct']} | **Latency:** {r['latency_s']}s\n\n")
            if r["error"]:
                f.write(f"**Error:** {r['error']}\n\n")

        # Failures section
        failures = [r for r in results if r["status"] != "PASS"]
        if failures:
            f.write("---\n\n## Failures\n\n")
            for r in failures:
                f.write(f"- **Test {r['num']}** ({r['category']}): {r['status']} - ")
                if r["error"]:
                    f.write(f"{r['error'][:200]}\n")
                elif not r["tool_correct"]:
                    f.write(f"called `{r['tool_called']}` instead of `{r['expected_tool']}`\n")
                else:
                    f.write(f"wrong args: {json.dumps(r['args'])[:200]}\n")

    # ── Write raw input/output text log ──────────────────────────────────
    raw_log_file = LOG_FILE.replace(".md", "_raw.txt")
    with open(raw_log_file, "w") as f:
        for entry in full_log_lines:
            f.write(entry)

    print(f"\nReport saved to: {LOG_FILE}")
    print(f"Raw I/O log saved to: {raw_log_file}")
    return passed, failed, errors


if __name__ == "__main__":
    p, f, e = run_tests()
    sys.exit(0 if f == 0 and e == 0 else 1)
