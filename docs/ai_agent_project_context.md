# AI Agent Project Context

This file is the fastest way for an AI agent to understand the current `job-vacancy-filter` project without reading the full repository.

## Project Summary

`job-vacancy-filter` is a local-first Streamlit app for:

- loading job vacancy data from CSV/XLSX or pasted text
- filtering and ranking jobs with transparent rule-based scoring
- uploading and analyzing a CV
- preparing manual-assisted applications
- generating personalized cover letters
- tracking application status locally

The app is intentionally manual-assisted.

## Safety Boundaries

Do not add or enable:

- mass auto-apply
- login scraping
- CAPTCHA bypass
- automatic submission to job sites

Allowed direction:

- import files
- parse pasted public text
- local CV analysis
- manual preparation workflows
- local persistence

## Current Runtime

- Python 3.11+
- Streamlit UI entrypoint: [app.py](C:/Users/RifkyAwalulHuda/Documents/GitHub/job-filter-py/app.py)
- Main local database: [job_vacancy_filter.db](C:/Users/RifkyAwalulHuda/Documents/GitHub/job-filter-py/job_vacancy_filter.db)
- Dependency list: [requirements.txt](C:/Users/RifkyAwalulHuda/Documents/GitHub/job-filter-py/requirements.txt)

## Main User Flows

### 1. Job Discovery

- user uploads CSV/XLSX, or
- user pastes lowongan text
- app normalizes the dataset
- user applies filters
- app calculates `match_score`
- user reviews ranked jobs
- user exports results to Excel

### 2. CV-Assisted Application Prep

- user uploads CV in PDF or DOCX
- app extracts basic profile details, skills, and a short experience summary
- app compares CV skills with selected job skills
- user selects cover letter tone and optional edit prompt
- app generates a manual-ready cover letter
- user opens the apply link manually

### 3. Local Tracking

- user profile is stored locally
- application status is stored locally
- persisted statuses are re-applied when jobs are loaded again

## Current Architecture

### UI Layer

- [app.py](C:/Users/RifkyAwalulHuda/Documents/GitHub/job-filter-py/app.py)
- owns Streamlit state, forms, search flow, preview flow, CV flow, and application assistant flow

### Core Modules

- [src/data_loader.py](C:/Users/RifkyAwalulHuda/Documents/GitHub/job-filter-py/src/data_loader.py)
  - loads CSV/XLS/XLSX
  - normalizes columns
  - ensures required schema

- [src/filters.py](C:/Users/RifkyAwalulHuda/Documents/GitHub/job-filter-py/src/filters.py)
  - `JobFilters`
  - `apply_filters(...)`

- [src/scoring.py](C:/Users/RifkyAwalulHuda/Documents/GitHub/job-filter-py/src/scoring.py)
  - `calculate_match_score(...)`
  - rule-based ranking

- [src/export_excel.py](C:/Users/RifkyAwalulHuda/Documents/GitHub/job-filter-py/src/export_excel.py)
  - Excel export to bytes using `openpyxl`

- [src/paste_jobs.py](C:/Users/RifkyAwalulHuda/Documents/GitHub/job-filter-py/src/paste_jobs.py)
  - parses pasted lowongan text
  - supports labeled and heuristic formats

- [src/cv_parser.py](C:/Users/RifkyAwalulHuda/Documents/GitHub/job-filter-py/src/cv_parser.py)
  - CV parsing from PDF/DOCX
  - skill extraction
  - experience summary extraction
  - CV vs job skill matching

- [src/cover_letter.py](C:/Users/RifkyAwalulHuda/Documents/GitHub/job-filter-py/src/cover_letter.py)
  - generates plain-text cover letters
  - supports tone selection and small edit prompts

- [src/profile.py](C:/Users/RifkyAwalulHuda/Documents/GitHub/job-filter-py/src/profile.py)
  - `UserProfile`
  - load/save profile via local DB helper

- [src/applications.py](C:/Users/RifkyAwalulHuda/Documents/GitHub/job-filter-py/src/applications.py)
  - status defaults and validation
  - overlays saved statuses onto DataFrames
  - persists status changes

- [src/database.py](C:/Users/RifkyAwalulHuda/Documents/GitHub/job-filter-py/src/database.py)
  - local persistence layer
  - prefers `SQLAlchemy` when available
  - automatically falls back to built-in `sqlite3` if `SQLAlchemy` is unavailable in the active runtime

## Important Persistence Behavior

The project currently stores only a limited set of persistent data:

- one local user profile
- application status per job
- optional stored cover letter text per application row

It does not yet persist:

- the full imported job dataset
- full CV history
- saved filter presets
- full application history UI

## Match Score Rules

Current score is simple and explicit:

- keyword match: `+25`
- location match: `+15`
- work mode match: `+15`
- job level match: `+10`
- salary suitable: `+15`
- each matched skill: `+5`, capped at `+20`

Sorting:

1. `match_score` descending
2. `posted_date` descending
3. `job_title` ascending

## Cover Letter Behavior

The generator is template-based and local-only.

It currently uses:

- applicant profile
- selected job
- matched CV skills
- missing job skills
- short CV experience summary
- chosen tone:
  - `formal`
  - `concise`
  - `confident`
- optional mini prompt such as:
  - `lebih formal`
  - `lebih singkat`
  - `lebih percaya diri`

Do not replace this with an external AI API unless explicitly requested.

## Pasted Jobs Preview Flow

Current behavior:

- pasted text is parsed into a preview DataFrame
- user can edit the preview in `st.data_editor`
- user explicitly applies the edited preview
- app then uses that edited data as the active source

This flow exists to reduce bad parse results before filtering/scoring.

## Error Handling Style

Project convention:

- use friendly `st.error(...)` or `st.warning(...)`
- do not show raw traceback in the UI
- keep fallback behavior graceful where practical

Examples already handled:

- invalid salary input
- unsupported upload format
- missing required job columns
- unreadable CV file
- unavailable PDF/DOCX parser dependency
- unavailable `SQLAlchemy` runtime

## Testing Status

The project already has a healthy pytest suite under [tests](C:/Users/RifkyAwalulHuda/Documents/GitHub/job-filter-py/tests).

Current areas covered:

- filters
- scoring
- cover letter
- pasted jobs parser
- CV parser
- application status helpers
- profile persistence

## Common Commands

Install dependencies:

```powershell
python -m pip install -r requirements.txt
```

Run tests:

```powershell
python -m pytest -q
```

Run app:

```powershell
python -m streamlit run app.py
```

## Current Known Limitations

- no official job source API integration yet
- no persistent multi-user support
- no browser automation for job submission
- CV parsing is still heuristic, not resume-grade NLP
- pasted jobs parsing is heuristic and may need user edits
- database currently persists only profile and application tracking basics

## Good Next Extensions

Safe directions for future work:

- save filter presets
- persist selected jobs or curated job lists
- add application notes and follow-up dates
- add richer CV skill normalization
- add better preview/edit controls for pasted jobs
- add application history views from SQLite

## Historical Note

Older docs in [docs/job_filter_app_codex_context_v2.md](C:/Users/RifkyAwalulHuda/Documents/GitHub/job-filter-py/docs/job_filter_app_codex_context_v2.md) and [docs/job_filter_app_prd_v2.md](C:/Users/RifkyAwalulHuda/Documents/GitHub/job-filter-py/docs/job_filter_app_prd_v2.md) are still useful for original intent, but they no longer reflect every current implementation detail.
