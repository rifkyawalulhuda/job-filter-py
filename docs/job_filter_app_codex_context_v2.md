# Codex Context v2 — Job Filter + Application Assistant

## New Modules to Add

### src/profile.py
- handle user profile
- save/load locally (json)

### src/cover_letter.py
function:
generate_cover_letter(job, profile)

### src/applications.py
- track application status
- update status

## UI Additions

Sidebar:
- upload CV
- input profile

Main:
- button: Prepare Application
- show generated cover letter
- button: Copy / Download

## Rules

- NO auto-submit without user action
- DO NOT implement scraping login sites
- DO NOT bypass captcha

## Implementation Notes

- store profile in local JSON
- store application tracking in dataframe column
- cover letter simple template string

## Goal

Turn the app into:
Filter → Select → Prepare → Apply (manual assist)
