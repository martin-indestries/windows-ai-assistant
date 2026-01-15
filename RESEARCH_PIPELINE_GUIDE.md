# Spectral Web Research Pipeline

## Overview

Spectral now includes a comprehensive, **free** web research pipeline that enables the AI to:

- 🔍 **Search the internet** using DuckDuckGo (no API keys required)
- 📄 **Fetch web pages** with intelligent fallback for JavaScript-heavy sites
- 📊 **Extract actionable information** including code blocks, commands, and common errors
- 🎯 **Synthesize knowledge packs** for task planning and execution
- 💾 **Cache results** to minimize redundant searches

**No paid APIs. No API keys. 100% free.**

## Features

### 1. Multi-Provider Search with Fallback
- **Primary**: DuckDuckGo HTML scraping
- **Fallback**: DuckDuckGo Lite for blocked requests
- Automatic provider switching
- Per-domain rate limiting (1-2 seconds)
- Maximum 5 results per query

### 2. Smart Content Fetching
- **Requests-based fetcher** (fast, ~1s per page)
- **Playwright fallback** for JavaScript-heavy pages (slower, ~5s per page)
- Automatic fallback triggers:
  - 403/429 status codes
  - Content < 500 characters
  - Empty text extraction

### 3. Intelligent Content Extraction
- Main content extraction using `readability-lxml` (with graceful fallback)
- Code block detection (Markdown and HTML)
- Heading extraction (h1, h2, h3)
- Meta description and title extraction
- Noise removal (nav, footer, sidebar, ads)

### 4. Knowledge Pack Synthesis
Structured information extracted into actionable format:
- **Goal**: One-sentence summary of task
- **Assumptions**: System/setup assumptions
- **Steps**: Focused, substantial steps with automation flags
- **Commands**: Specific commands with platform info
- **File paths**: Important files with purposes
- **Settings**: Configuration values and locations
- **Common errors**: Known issues with solutions
- **Sources**: URLs and evidence for verification

### 5. Intelligent Caching
- **Web cache**: 14 days (fetched pages)
- **Search cache**: 7 days (search results)
- **Knowledge packs**: 30 days (synthesized information)
- SQLite-based persistent storage
- Deduplication by query hash

## Usage

### Example Queries

#### Information Gathering (RESEARCH mode)
```
"How do I install Python on Windows?"
"What is ECONNREFUSED error in Node.js?"
"Does Flask support async routes?"
"What are the best practices for SQLite in Python?"
```

**Response**: Formatted knowledge pack with steps, commands, sources

#### Research + Action (RESEARCH_AND_ACT mode)
```
"How to set up GitHub Actions for Python and create the workflow file"
"Find out how to install Flask then build a hello world app"
```

**Response**: Research results + optional execution of automated steps

### Programmatic Usage

```python
from spectral.research import ResearchOrchestrator

# Initialize orchestrator
orchestrator = ResearchOrchestrator(
    enable_playwright=False  # Set True for JS-heavy pages
)

# Run research
pack = orchestrator.run_research(
    query="How to install Python on Windows",
    max_pages=5,
    force_refresh=False  # Use cache if available
)

# Access results
print(f"Goal: {pack.goal}")
print(f"Confidence: {pack.confidence}")

for step in pack.steps:
    print(f"Step: {step['title']}")
    print(f"  {step['description']}")

for cmd in pack.commands:
    print(f"Command: {cmd['command_text']}")
    print(f"  Platform: {cmd['platform']}")
```

### Integrated Chat Flow

The research pipeline automatically activates when you ask:
- Questions starting with "how", "what", "why", "when", "where", "can", "does"
- Setup/installation queries
- Error/troubleshooting requests
- Configuration questions

**Example Chat Session**:
```
User: How do I install Flask on Windows?
Spectral: 🔍 Researching: How do I install Flask on Windows?

📚 Research Results: Install Flask web framework on Windows

**Steps:**
1. **Verify Python Installation**
   Check that Python 3.7+ is installed
2. **Install Flask via pip**
   Use pip package manager to install Flask
3. **Verify Installation**
   Import Flask in Python to confirm

**Commands:**
  [windows] `python --version`
     → Check Python version
  [windows] `pip install flask`
     → Install Flask package
  [windows] `python -c "import flask; print(flask.__version__)"`
     → Verify Flask installation

**Sources:**
  [1] Flask Installation — Flask Documentation
      https://flask.palletsprojects.com/en/latest/installation/
  [2] Python Packages Installation - Real Python
      https://realpython.com/installing-python/

Confidence: 90%
```

## Architecture

### Module Structure
```
src/spectral/research/
├── __init__.py                  # Public API exports
├── knowledge_pack.py            # Data models (KnowledgePack, SourceEvidence, etc.)
├── search_providers.py          # DuckDuckGo scrapers with fallback
├── fetcher.py                   # Requests + Playwright fetchers
├── extractor.py                 # Content extraction (BeautifulSoup + readability)
└── research_orchestrator.py    # Main orchestration logic
```

### Execution Flow
```
User Query
    ↓
Execution Router (classify intent)
    ↓
Research Intent Detected?
    ↓ Yes
Research Handler
    ↓
Search Provider Chain (DDG → DDG Lite)
    ↓
Smart Fetcher (Requests → Playwright fallback)
    ↓
Content Extractor (readability → heuristic)
    ↓
LLM Synthesis (structure knowledge pack)
    ↓
Cache Results
    ↓
Format & Display
```

### Database Schema

**web_cache**:
- Stores fetched page content
- TTL: 14 days
- Keyed by URL

**search_cache**:
- Stores search results
- TTL: 7 days
- Keyed by query

**knowledge_packs**:
- Stores synthesized knowledge
- TTL: 30 days
- Keyed by query hash (deduplication)

## Configuration

### Playwright Setup (Optional)

For JavaScript-heavy pages, install Playwright browsers:

```bash
pip install playwright
playwright install chromium
```

**Enable in code**:
```python
orchestrator = ResearchOrchestrator(enable_playwright=True)
```

### Cache Location

Default: `~/.spectral/cache/research_cache.db`

**Custom path**:
```python
from pathlib import Path

orchestrator = ResearchOrchestrator(
    cache_db_path=Path("/path/to/cache.db")
)
```

## Testing

### Unit Tests
```bash
pytest tests/research/
```

### Quick Validation (Live Test)
```bash
python tests/research/run_quick_validation.py
```

This runs a real research query to validate the full pipeline end-to-end.

## Performance

### Typical Research Query
- Search: 1-2 seconds
- Fetch 5 pages: 5-10 seconds (requests) or 25-50 seconds (Playwright)
- Extraction: <1 second per page
- LLM synthesis: 2-5 seconds
- **Total**: 10-20 seconds (without Playwright), 30-60 seconds (with Playwright)

### Optimizations
- Cache hit avoids search + fetch: <1 second response
- Rate limiting prevents blocks: 1s cooldown per domain
- Requests-first approach: 10x faster than Playwright

## Privacy & Safety

✅ **No user data logging**: Only query topics and domains accessed are logged
✅ **No automatic binary downloads**: User approval required
✅ **Respects robots.txt**: Adds cooldown for restricted domains
✅ **User-Agent**: Desktop Chrome (not bot-identified)

## Limitations

- **Max 5 results per search**: Keeps research fast and focused
- **No real-time data**: Cache may be stale (up to 30 days for packs)
- **DuckDuckGo only**: No Google, Bing, or other search engines
- **English-focused**: Better results for English content
- **Text-only**: No image, video, or PDF processing

## Troubleshooting

### Search providers blocked (403/429)
- Automatic fallback to DuckDuckGo Lite
- If both fail, cache may still provide results
- Wait 5-10 minutes and retry

### Playwright not working
- Ensure Playwright browsers installed: `playwright install chromium`
- Check system compatibility (requires ~200MB disk space)
- Fallback: Disable Playwright (`enable_playwright=False`)

### Empty/poor results
- Try more specific queries
- Check internet connectivity
- Force refresh to bypass stale cache: `force_refresh=True`

### LLM synthesis errors
- Falls back to manual knowledge pack with sources listed
- Check LLM client configuration (Ollama running?)

## Future Enhancements

- [ ] Multi-language support
- [ ] PDF/document parsing
- [ ] Image extraction and description
- [ ] More search providers (Bing Lite, etc.)
- [ ] Vector embeddings for similarity search
- [ ] Pack validation and confidence scoring improvements

## Examples

See `tests/research/run_quick_validation.py` for a complete working example.

## Dependencies

Installed automatically with Spectral:
- `beautifulsoup4>=4.11.0` - HTML parsing
- `lxml>=4.9.0` - XML processing
- `readability-lxml>=0.8.1` - Content extraction
- `playwright>=1.40.0` - JavaScript rendering (optional)
- `requests>=2.28.0` - HTTP client

---

**Built with ❤️ for Spectral** - No API keys, no limits, no paywalls.
