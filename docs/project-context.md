# AI Job Vacancy Filter

**job-filter-py** — Streamlit app untuk mencari lowongan kerja secara otomatis dari LinkedIn Indonesia, dilengkapi filter, scoring, cover letter generation, dan AI enrichment via BYOK LLM.

## Arsitektur

```
job-filter-py/
├── app.py                       ← Streamlit UI (entry point)
├── bin/
│   ├── obscura.exe              ← Headless browser engine (Rust + V8)
│   └── obscura-worker.exe       ← Worker for parallel scraping
├── src/
│   ├── job_search.py            ← Multi-platform search orchestrator
│   │   ├── LinkedInBackend      ← LinkedIn job search via Obscura
│   │   ├── ObscuraBackend       ← Bing search via Obscura
│   │   ├── GoogleBackend        ← Google search (JS-only, not used)
│   │   ├── YahooBackend         ← Yahoo search (rate-limited)
│   │   ├── DuckDuckGoBackend    ← DDG search (blocked on this machine)
│   │   ├── LLMSearchBackend     ← AI search via BYOK LLM
│   │   ├── _fetch_job_details() ← Scrape detail pages for full descriptions
│   │   └── search_jobs()        ← Multi-platform orchestrator
│   ├── llm.py                   ← LLM client + BYOK config + AI features
│   │   ├── LLMConfig            ← API key, endpoint, model (persisted to SQLite)
│   │   ├── LLMClient            ← OpenAI-compatible HTTP client
│   │   ├── generate_ai_cover_letter()  ← AI cover letter (language-aware)
│   │   ├── ai_enhance_jobs()    ← LLM infers skills, level, salary from scraped data
│   │   ├── ai_generate_profile_summary() ← AI professional summary
│   │   └── ai_generate_cv()     ← AI full CV generator
│   ├── filters.py               ← Filter lowongan (keyword, lokasi, gaji, skills)
│   ├── scoring.py               ← Skor & ranking hasil filter (0-100)
│   ├── cover_letter.py          ← Template cover letter (bilingual: EN/ID)
│   ├── cv_parser.py             ← Parse CV (PDF/DOCX/text/markdown)
│   │   ├── analyze_cv_bytes()   ← Parse uploaded PDF/DOCX
│   │   └── analyze_profile_text() ← Parse user-typed text/markdown profile
│   ├── applications.py          ← Application status tracking
│   ├── profile.py               ← User profile CRUD (SQLite)
│   ├── database.py              ← SQLite persistence (SQLAlchemy + raw fallback)
│   ├── data_loader.py           ← CSV/Excel loader (legacy, unused by main app)
│   ├── paste_jobs.py            ← Paste job text parser (legacy, unused by main app)
│   └── export_excel.py          ← Export hasil ke Excel
├── tests/                       ← 72 unit tests
├── docs/
│   └── project-context.md       ← This file
├── data/
│   └── sample_jobs.csv          ← Sample dataset (legacy)
├── requirements.txt
└── job_vacancy_filter.db        ← SQLite database (auto-created)
```

## Workflow

```
┌─────────────────────────────────────────────────────────────┐
│ SIDEBAR                                                      │
│                                                              │
│ ▼ Search Filters (expanded)                                  │
│   Keyword, Location, Work mode, Job level, Skills            │
│   ▶ Salary & Date                                            │
│                                                              │
│ [ Search Jobs ]  ← primary blue button                       │
│                                                              │
│ ▶ Profile & CV (collapsed)                                   │
│   Profile form (Name, Email, Phone, LinkedIn, Portfolio)     │
│   ◉ Upload PDF/DOCX  ○ Write Markdown/Text                   │
│   [Use CV Details] / [Parse & Use Text Profile]              │
│   [AI Generate Summary] [AI Generate CV]                     │
│                                                              │
│ ▶ CV Insights (collapsed, after CV parsed)                   │
│                                                              │
│ ▶ AI Settings (collapsed)                                    │
│   API Base URL, API Key, Model                               │
│   [✓] AI-Powered Cover Letter                                │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│ AI SEARCH PIPELINE                                            │
│                                                               │
│ Phase 1a: LinkedIn Discovery                                  │
│   obscura fetch "id.linkedin.com/jobs/search?keywords=..."    │
│   → 60+ individual jobs (title, company, location, URL)       │
│                                                               │
│ Phase 1b: Bing Discovery (supplementary)                      │
│   obscura fetch "bing.com/search?q=lowongan+pekerjaan+..."    │
│   → Additional job URLs                                       │
│                                                               │
│ Phase 2: Detail Scraping (15 jobs)                            │
│   for each linkedin.com/jobs/view/ URL:                       │
│     obscura fetch → extract full description                  │
│                                                               │
│ Phase 3: AI Enrichment (if BYOK configured)                   │
│   LLM infers: skills, job_level, work_mode, salary, desc      │
│                                                               │
│ Phase 4: Filter + Score                                       │
│   apply_filters() + calculate_match_score()                   │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│ MAIN AREA                                                     │
│                                                               │
│ ┌──────────┐ ┌──────────┐ ┌──────────┐                       │
│ │ Results  │ │ Avg Score│ │ Searched │  ← metric cards        │
│ └──────────┘ └──────────┘ └──────────┘                       │
│                                                               │
│ Filtered Results (DataFrame)                                  │
│ [Download Excel]                                              │
│                                                               │
│ ───────────────────────────────────────────                   │
│ Application Assistant                                         │
│   Select a job → Cover letter tone → Edit prompt              │
│   [Prepare Application]                                       │
│   Generated Cover Letter (editable)                           │
│   [Download Cover Letter] [Open Apply Link] [Mark Submitted]  │
└─────────────────────────────────────────────────────────────┘
```

## Cara Menjalankan

```bash
cd E:\Github\job-filter-py
pip install -r requirements.txt
streamlit run app.py
```

## Dependencies

```
streamlit>=1.58
pandas
openpyxl
pytest
pypdf
python-docx
SQLAlchemy
requests
```

External binary: `bin/obscura.exe` v0.1.8 (headless browser, 70 MB)
Download: https://github.com/h4ckf0r0day/obscura/releases

## Schema Lowongan

| Kolom | Tipe | Deskripsi |
|---|---|---|
| `job_title` | text | Judul lowongan (required) |
| `company` | text | Nama perusahaan (required) |
| `location` | text | Lokasi |
| `work_mode` | text | remote / hybrid / onsite |
| `job_level` | text | internship / entry / junior / mid / senior / lead / manager |
| `salary_min` | numeric | Gaji minimum |
| `salary_max` | numeric | Gaji maksimum |
| `currency` | text | Mata uang (IDR/USD) |
| `skills` | text | Skills (semicolon-separated) |
| `posted_date` | date | Tanggal posting |
| `job_type` | text | full-time / part-time / contract |
| `apply_url` | text | URL lamaran |
| `description` | text | Deskripsi lowongan (dari detail page) |

## AI Search — Multi-Platform

### Phase 1: Discovery

| Platform | Status | Metode |
|---|---|---|
| **LinkedIn Indonesia** | ✅ Primary | `id.linkedin.com/jobs/search` via Obscura — 60+ individual jobs |
| **Bing (supplementary)** | ✅ Fallback | `bing.com/search?q=lowongan+pekerjaan+...` via Obscura |
| Glints | ❌ SPA | Next.js JS errors, not scrapeable |
| Kalibrr | ❌ SPA | Heavy SPA, not scrapeable |
| Jobstreet | ❌ SPA | Redirect to homepage, not scrapeable |

### Phase 2: Detail Scraping

- `_fetch_job_details()` — scrapes 15 job detail pages via Obscura
- Extracts: full job description, verified company name, location
- Rate-limited: 1.5s between fetches

### Phase 3: AI Enrichment (BYOK)

- `ai_enhance_jobs()` — LLM infers from title+company:
  - `skills`: relevant tech stack
  - `job_level`: internship/entry/junior/mid/senior/lead/manager
  - `work_mode`: remote/hybrid/onsite
  - `salary_min`/`salary_max`: realistic IDR range
  - `description`: 1-2 sentence job summary

## AI Features (BYOK)

| Fitur | Fungsi | Lokasi |
|---|---|---|
| AI Cover Letter | LLM generate personalized, language-aware | Application Assistant |
| AI Enhance Jobs | LLM infers skills, level, salary from scraped data | After search |
| AI Generate Summary | LLM professional profile summary | Profile & CV section |
| AI Generate CV | LLM full ATS-friendly CV | Profile & CV section |

### Language Detection

AI dan template cover letter mendeteksi bahasa dari custom prompt:
- `lebih formal, singkat` → Indonesian
- `more formal, concise` → English
- (kosong) → English default

## BYOK Configuration

- Panel: Sidebar → AI Settings
- Fields: API Base URL, API Key, Model
- Persistence: SQLite (`llm_config` table)
- Compatible: OpenAI, dough.id, Groq, any OpenAI-compatible endpoint
- Supports reasoning models (deepseek-v4-pro, o1) — reads `reasoning_content` field

## UI Design

- **Style**: Executive Dashboard + Minimal & Direct (ui-ux-pro-max)
- **Theme**: Streamlit native light/dark mode (no hardcoded colors)
- **Structure**: Collapsible sidebar sections with `st.expander`
- **Notifications**: `st.toast()` native floating notifications
- **Metrics**: Card-style KPI cards with uppercase labels
- **Buttons**: Rounded 8px, opacity transitions
- **DataFrame**: Rounded 10px border with overflow hidden

## Testing

```bash
python -m pytest tests/ -v
```

**72 tests**, mencakup semua modul:
- `test_job_search.py` (24 tests)
- `test_filters.py` (12 tests)
- `test_scoring.py` (8 tests)
- `test_cover_letter.py` (12 tests)
- `test_cv_parser.py` (4 tests)
- `test_paste_jobs.py` (4 tests)
- `test_applications.py` (5 tests)
- `test_profile.py` (2 tests)

## Status Development

| Fitur | Status |
|---|---|
| Multi-platform job search (LinkedIn + Bing) | ✅ Production |
| Detail page scraping (full job description) | ✅ Production |
| AI enrichment (skills, level, salary) | ✅ Production (BYOK) |
| AI Cover Letter (language-aware) | ✅ Production (BYOK) |
| AI Profile Summary / CV Generator | ✅ Production (BYOK) |
| Template cover letter (bilingual) | ✅ Production |
| Filter & Scoring | ✅ Production |
| CV Parser (PDF + text/markdown) | ✅ Production |
| Application Tracking | ✅ Production |
| Excel Export | ✅ Production |
| Profile Management | ✅ Production |
| BYOK LLM Configuration | ✅ Production |
| Toast notifications (`st.toast()`) | ✅ Production |
| Dark/Light mode (Streamlit native) | ✅ Production |
| CSV/Excel Upload | ❌ Removed (migrated to AI search) |
| Paste Jobs | ❌ Removed (migrated to AI search) |

## Catatan Teknis

- **Python**: 3.11 (windows-x86_64)
- **Streamlit**: 1.58+ (uses `st.toast()`)
- **Database**: SQLite (`job_vacancy_filter.db` di project root)
  - Tables: `user_profiles`, `applications`, `llm_config`
- **Mesin**: Windows 10
  - DuckDuckGo: blocked at SSL level
  - Google/Bing: JS-rendered (requires Obscura headless browser)
  - Yahoo: rate-limited
- **Headless Browser**: Obscura v0.1.8 (Rust + V8, 30 MB memory)
  - Location: `bin/obscura.exe`
  - Used for: LinkedIn search, Bing search, detail page scraping
- **Provider LLM**: dough.id (`mimo/mimo-v2.5`) via `api.tokenrouter.com/v1`
  - Also tested: `deepseek/deepseek-v4-pro` (reasoning model)
  - Supports: any OpenAI-compatible endpoint
- **Shell**: Git Bash (MSYS) — POSIX syntax, NOT PowerShell
