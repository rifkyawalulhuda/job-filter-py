# PRD — Job Vacancy Filter App (v2 with Application Assistant)

## New Feature: Application Assistant (MVP 2)

### Tujuan
Menambahkan kemampuan untuk membantu user menyiapkan dan mengelola lamaran kerja secara semi-otomatis.

### Scope Feature

1. User Profile
- Nama
- Email
- Phone
- LinkedIn URL
- Portfolio URL

2. CV Upload
- Upload file PDF/DOCX
- Bisa memilih CV aktif

3. Cover Letter Generator
- Template berbasis input user
- Generate otomatis dari:
  - job_title
  - company
  - skills

4. Application Tracker
Tambahkan kolom:
- application_status:
  - Not Applied
  - Draft Ready
  - Submitted
  - Failed

5. Draft Application
User dapat:
- memilih job dari hasil filter
- klik "Prepare Application"
- sistem generate:
  - cover letter
  - bundle data lamaran

6. Submission (Manual First)
- Tombol:
  - Open Apply Link
  - Copy Cover Letter
- Tidak auto-submit tanpa user interaction

### Out of Scope
- Auto apply ke LinkedIn/Indeed
- Bypass login/captcha
- Bot mass apply

### Future (Phase 3)
- Semi-auto submit via API resmi
- Batch apply dengan konfirmasi
