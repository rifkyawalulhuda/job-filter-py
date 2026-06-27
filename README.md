# AI Job Vacancy Filter

AI-powered job search across 6 platforms (LinkedIn, Indeed, Google Jobs, Glints, Kalibrr, Bing) with filtering, scoring, cover letter generation, and AI enrichment via BYOK LLM.

## Features

- **Multi-platform job search** — 6 platforms in parallel via Obscura headless browser
- **Detail scraping** — Full job descriptions from individual job pages
- **AI enrichment** — LLM infers skills, job level, work mode, and salary range
- **Filter & score** — Token-based keyword matching, location/work-mode/job-level tolerance for non-LinkedIn platforms
- **Cover letter** — Template or AI-generated (language-aware: EN/ID)
- **CV parser** — Upload PDF/DOCX or paste text/markdown
- **Application tracking** — Per-job status: Not Applied → Draft Ready → Submitted
- **AI Profile/CV generation** — LLM generates professional summary and full CV
- **Excel export** — Download filtered results

## Quick Start

```bash
# Install dependencies
pip install -r requirements.txt

# Download Obscura headless browser (required for search)
# https://github.com/h4ckf0r0day/obscura/releases/latest
# Extract obscura.exe + obscura-worker.exe → bin/

# Run the app
streamlit run app.py
```

## BYOK AI Configuration

From sidebar → AI Settings, configure your LLM:

| Field | Example |
|---|---|
| API Base URL | `https://api.tokenrouter.com/v1` |
| API Key | `sk-...` |
| Model | `deepseek/deepseek-v4-pro` |

Compatible with any OpenAI-compatible endpoint (dough.id, Groq, OpenRouter, etc.).

## Architecture

```
app.py                         ← Streamlit UI
src/
├── job_search.py              ← 6-platform parallel search orchestrator
├── filters.py                 ← Token-based keyword matching + filter tolerance
├── scoring.py                 ← 0-100 match score
├── cover_letter.py            ← Bilingual template (EN/ID)
├── cv_parser.py               ← PDF/DOCX/text/markdown parsing
├── llm.py                     ← BYOK LLM client + AI features
├── applications.py            ← Application status tracking
├── profile.py                 ← User profile CRUD
├── database.py                ← SQLite persistence
├── data_loader.py             ← CSV/Excel loader (legacy)
├── paste_jobs.py              ← Paste job text parser (legacy)
└── export_excel.py            ← Excel export
bin/
├── obscura.exe                ← Headless browser (Rust + V8, 70 MB)
└── obscura-worker.exe         ← Worker for parallel scraping
```

## Search Pipeline

```
search_jobs("Python Developer Jakarta")
    │
    ├── Thread 1: LinkedIn  → 60+ individual jobs + full description
    ├── Thread 2: Indeed    → 5+ individual jobs
    ├── Thread 3: Google    → 10+ jobs (rate-limited, silent fail)
    ├── Thread 4: Glints    → Index page results
    ├── Thread 5: Kalibrr   → Index page results
    └── Thread 6: Bing      → Supplementary URLs

    ALL 6 THREADS RUN IN PARALLEL
    → Dedup → Detail scrape (LinkedIn) → AI enrich (BYOK) → Filter → Score
```

## Schema

| Column | Type | Description |
|---|---|---|
| `job_title` | text | Job title (required) |
| `company` | text | Company name (required) |
| `location` | text | Location |
| `work_mode` | text | remote / hybrid / onsite |
| `job_level` | text | internship / entry / junior / mid / senior / lead / manager |
| `salary_min` | numeric | Minimum salary |
| `salary_max` | numeric | Maximum salary |
| `currency` | text | Currency (IDR/USD) |
| `skills` | text | Skills (semicolon-separated) |
| `posted_date` | date | Posted date |
| `job_type` | text | full-time / part-time / contract |
| `apply_url` | text | Apply URL |
| `description` | text | Job description |

## Testing

```bash
python -m pytest tests/ -v
```

**75 tests**, covering all modules.

## Local Storage

- Database: `job_vacancy_filter.db` (SQLite)
- Tables: `user_profiles`, `applications`, `llm_config`

## Safety

- No mass auto-apply
- No CAPTCHA bypass
- No login scraping
- Submission remains manual-assisted

## Technical Notes

- **Python**: 3.11+ (windows-x86_64)
- **Streamlit**: 1.58+ (uses `st.toast()`, `st.expander`)
- **Headless Browser**: Obscura v0.1.8 (Rust + V8, 30 MB memory)
- **UI/UX**: Executive Dashboard style, native Streamlit dark/light mode
- **Notifications**: Floating toast via `st.toast()`
- **Sidebar**: Collapsible sections via `st.expander`
