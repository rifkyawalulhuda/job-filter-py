# Job Vacancy Filter

Job Vacancy Filter is a Streamlit tool for reviewing job vacancies, ranking them with simple matching logic, and preparing manual-assisted application drafts.

## Current Highlights

- Upload CSV/XLSX job data or paste lowongan text directly
- Filter and rank jobs with a transparent `match_score`
- Persist profile data and application statuses locally with `SQLite + SQLAlchemy`
- Upload a CV and extract basic contact details, skills, and a short experience summary
- Compare CV skills with the selected job
- Generate a more personal cover letter with:
  - a short reason why the role looks like a fit
  - a short candidate experience summary from the CV
  - selectable tone: `formal`, `concise`, or `confident`
  - a small free-text edit prompt such as `lebih formal` or `lebih singkat`

## Safety

- no mass auto-apply
- no CAPTCHA bypass
- no login scraping
- submission remains manual-assisted

## Run

```bash
python -m streamlit run app.py
```

## Local Storage

- The app now stores profile data and application statuses in a local SQLite database file: `job_vacancy_filter.db`
- This keeps the setup simple for one machine today while staying easy to extend later
