# Install Dependencies

Panduan ini menjelaskan cara menginstall semua modul yang dibutuhkan oleh project `job-vacancy-filter`.

## Lokasi Project

Buka PowerShell lalu masuk ke folder project:

```powershell
cd C:\Users\RifkyAwalulHuda\Documents\GitHub\job-filter-py
```

## Opsi 1: Install Langsung

Cara paling cepat:

```powershell
python -m pip install -r requirements.txt
```

## Opsi 2: Install Dengan Virtual Environment

Cara ini lebih rapi dan direkomendasikan:

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

## Jika PowerShell Menolak Aktivasi

Kalau muncul error saat menjalankan `.venv\Scripts\Activate.ps1`, jalankan:

```powershell
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
```

Lalu tutup dan buka lagi PowerShell, kemudian aktifkan lagi:

```powershell
.venv\Scripts\Activate.ps1
```

## Cek Modul Sudah Terpasang

Untuk memastikan modul penting sudah terinstall:

```powershell
python -m pip show streamlit pandas openpyxl pytest SQLAlchemy
```

## Menjalankan App

Setelah dependency selesai diinstall:

```powershell
python -m streamlit run app.py
```

## File Requirements

Project ini memakai dependency dari file berikut:

- `requirements.txt`

Isi utamanya saat ini mencakup:

- `streamlit`
- `pandas`
- `openpyxl`
- `pytest`
- `pypdf`
- `python-docx`
- `SQLAlchemy`

## Catatan

- Jika app dibuka dari environment Python yang berbeda, beberapa modul bisa terlihat seperti belum terinstall.
- Untuk menghindari itu, jalankan app dan install dependency dari interpreter Python yang sama.
- Cara paling aman adalah selalu memakai:

```powershell
python -m pip install -r requirements.txt
python -m streamlit run app.py
```
