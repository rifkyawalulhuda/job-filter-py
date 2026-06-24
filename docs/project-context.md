# 🤖 AI Job Vacancy Filter

**job-filter-py** — Streamlit app untuk mencari, memfilter, dan menyiapkan lamaran lowongan kerja secara manual. Tidak auto-submit, tidak scraping, tidak CAPTCHA bypass.

## Arsitektur

```
app.py                         ← Streamlit UI (entry point)
src/
├── job_search.py              ← AI-powered search (Yahoo scraping / LLM backend)
├── filters.py                 ← Filter lowongan (keyword, lokasi, gaji, skills, dll)
├── scoring.py                 ← Skor & ranking hasil filter (0-100)
├── data_loader.py             ← Load CSV/Excel & normalisasi schema (legacy)
├── paste_jobs.py              ← Parse teks lowongan yang di-paste (legacy)
├── cover_letter.py            ← Generate draft cover letter
├── cv_parser.py               ← Parse CV (PDF/DOCX) → skills, kontak, summary
├── applications.py            ← Application status tracking (Not Applied → Submitted)
├── profile.py                 ← User profile CRUD (SQLite)
├── database.py                ← SQLite persistence (SQLAlchemy + raw sqlite3 fallback)
└── export_excel.py            ← Export hasil ke Excel
tests/
├── test_job_search.py
├── test_filters.py
├── test_scoring.py
├── test_cover_letter.py
├── test_cv_parser.py
├── test_paste_jobs.py
├── test_applications.py
└── test_profile.py
```

## Workflow

```
User isi filter di sidebar (keyword, lokasi, level, work mode, skills)
        │
        ▼
Klik "🔍 AI Search Jobs"
        │
        ▼
  search_jobs() ──► LLM (dough.id) ──► structured JSON job listings
        │
        ▼
  apply_filters() + calculate_match_score()
        │
        ▼
  Hasil ditampilkan ──► 📥 Export Excel ──► ✨ Prepare Cover Letter ──► ✅ Mark Submitted
```

## Cara Menjalankan

```bash
cd E:\Github\job-filter-py
pip install -r requirements.txt
streamlit run app.py
```

## Dependencies

```
streamlit
pandas
openpyxl
pytest
pypdf
python-docx
SQLAlchemy
requests
```

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
| `description` | text | Deskripsi lowongan |

## AI Search Backend

Saat ini menggunakan **Yahoo** sebagai default backend (gratis, tanpa API key). Fallback ke **LLM** (dough.id `mimo/mimo-v2.5`) jika web scraping gagal.

Backend yang tersedia (pluggable via `SearchBackend` protocol):

| Backend | Status | Keterangan |
|---|---|---|
| `YahooBackend` | ✅ Default | Bekerja di mesin ini |
| `DuckDuckGoBackend` | ❌ Blocked | SSL handshake diblokir firewall |
| `GoogleBackend` | ❌ JS-only | Return halaman kosong (SPA) |
| `LLMBackend` | 🚧 TODO | Gunakan dough.id LLM |

## Testing

```bash
python -m pytest tests/ -v
```

**72 tests**, mencakup semua modul.

## Status Development

| Fitur | Status |
|---|---|
| AI Job Search | ✅ Production |
| Filter & Scoring | ✅ Production |
| Cover Letter Generator | ✅ Production |
| CV Parser (PDF/DOCX) | ✅ Production |
| Application Tracking | ✅ Production |
| Excel Export | ✅ Production |
| Profile Management | ✅ Production |
| CSV/Excel Upload | ❌ Dihapus (migrasi ke AI search) |
| Paste Jobs | ❌ Dihapus (migrasi ke AI search) |
| LLM Backend | 🚧 TODO |
| Multi-backend fallback | 🚧 TODO |

## Catatan Teknis

- **Python**: 3.11 (windows-x86_64)
- **Database**: SQLite (`job_vacancy_filter.db` di project root)
- **Mesin**: Windows 10, DuckDuckGo diblokir di level SSL
- **Provider LLM**: dough.id (`mimo/mimo-v2.5`) via custom OpenAI-compatible endpoint
