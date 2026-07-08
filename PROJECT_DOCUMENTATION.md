# CaseDesk — Complete Project Documentation

> **CaseDesk** is a full-stack, locally-hosted case file management system designed for processing, storing, searching, and analysing investigation case documents. It automatically extracts structured metadata from uploaded PDFs, DOCX files, and scanned images using OCR and NLP, stores them in a MySQL database, and presents them through a dark-themed web dashboard with analytics, search, review workflows, and PDF export capabilities.

---

## Table of Contents

1. [Project Overview](#1-project-overview)
2. [Architecture Overview](#2-architecture-overview)
3. [Technology Stack & Why Each Was Chosen](#3-technology-stack--why-each-was-chosen)
4. [Project File Structure](#4-project-file-structure)
5. [Database Schema](#5-database-schema)
6. [Backend — Detailed Breakdown](#6-backend--detailed-breakdown)
7. [Frontend — Detailed Breakdown](#7-frontend--detailed-breakdown)
8. [API Reference](#8-api-reference)
9. [Features](#9-features)
10. [Authentication & Security](#10-authentication--security)
11. [Document Extraction Pipeline](#11-document-extraction-pipeline)
12. [Setup & Reproduction Guide](#12-setup--reproduction-guide)
13. [Environment Variables](#13-environment-variables)
14. [Running the Application](#14-running-the-application)
15. [Troubleshooting](#15-troubleshooting)

---

## 1. Project Overview

**CaseDesk** is built to solve the problem of manually managing large volumes of physical/scanned case documents. Instead of officers manually reading every document to catalogue it, CaseDesk:

1. **Ingests** case files (PDFs, DOCX, images) from a local folder structure or direct uploads.
2. **Extracts** text using digital PDF parsing, OCR (for scanned documents), and DOCX parsing.
3. **Parses** the extracted text with regex patterns and NLP (spaCy) to automatically identify structured fields: officer name, date, location, incident type, complainant, suspect, evidence, notes, analyst, investigating officer, service numbers, unit names, military commands, suspected PIO phone numbers, and various dates.
4. **Validates** each extraction — flagging cases with empty text, too few parsed fields, low OCR confidence, or extraction exceptions.
5. **Stores** everything in a MySQL database with per-file tracking.
6. **Displays** cases in a rich web dashboard with full search, filtering, year-based grouping, analytics charts, a manual review queue, a timeline view, inline document previews, PDF export, and admin user management.

The application is designed to run **entirely locally** on a Windows machine — no cloud services or external APIs required.

---

## 2. Architecture Overview

```
┌──────────────────────────────────────────────────────────────┐
│                        BROWSER (Frontend)                    │
│  HTML + Vanilla CSS + Vanilla JavaScript + Chart.js          │
│  Served by Python's built-in HTTP server on port 5500        │
└─────────────────────────┬────────────────────────────────────┘
                          │ HTTP (REST API calls via fetch)
                          │ JWT Bearer token in Authorization header
                          ▼
┌──────────────────────────────────────────────────────────────┐
│                     FastAPI Backend (port 8000)               │
│  ┌───────────────────────────────────────────────────────┐   │
│  │  Routers: auth, upload, cases, review, analytics,     │   │
│  │           export                                      │   │
│  ├───────────────────────────────────────────────────────┤   │
│  │  Extractor Pipeline:                                  │   │
│  │    detect → pdf_extractor / docx_extractor /          │   │
│  │             image_extractor → field_parser            │   │
│  │    folder_scanner (bulk ingest)                       │   │
│  ├───────────────────────────────────────────────────────┤   │
│  │  Auth: bcrypt password hashing + JWT (python-jose)    │   │
│  │  Validator: post-extraction quality checks            │   │
│  ├───────────────────────────────────────────────────────┤   │
│  │  ORM: SQLAlchemy                                      │   │
│  │  Database Driver: PyMySQL                             │   │
│  └───────────────────────────────────────────────────────┘   │
└─────────────────────────┬────────────────────────────────────┘
                          │ SQL via SQLAlchemy ORM
                          ▼
┌──────────────────────────────────────────────────────────────┐
│                    MySQL Database                             │
│  Tables: cases, case_files, users, audit_logs                │
└──────────────────────────────────────────────────────────────┘
```

**Key architectural decisions:**

- **Separation of concerns:** Backend (API + extraction) and frontend (static HTML/JS) are completely decoupled and communicate via REST.
- **No build tools:** The frontend uses no framework, no bundler, no npm — just plain HTML/CSS/JS. This keeps it dead simple to deploy and modify.
- **Local-first:** Everything runs on localhost. The `.env` file configures the DB connection, paths to Tesseract and Poppler, and allowed CORS origins.
- **Background processing:** Folder scans run as FastAPI `BackgroundTasks` with a `ThreadPoolExecutor` for concurrent file processing.

---

## 3. Technology Stack & Why Each Was Chosen

### Backend

| Technology | Version / Package | Why |
|---|---|---|
| **Python** | 3.10+ | Industry standard for data processing, NLP, and OCR tasks. Rich ecosystem of document processing libraries. |
| **FastAPI** | `fastapi` | High-performance async web framework with automatic OpenAPI docs, dependency injection, and native Pydantic integration. |
| **Uvicorn** | `uvicorn[standard]` | ASGI server for FastAPI. Supports hot-reload during development. |
| **SQLAlchemy** | `sqlalchemy` | Battle-tested Python ORM. Declarative models, session management, and database migrations. |
| **PyMySQL** | `pymysql` | Pure-Python MySQL driver — no C extensions to compile, simpler Windows setup. |
| **python-dotenv** | `python-dotenv` | Loads environment variables from `.env` file — keeps secrets out of code. |
| **passlib + bcrypt** | `passlib[bcrypt]`, `bcrypt` | Industry-standard password hashing. Bcrypt is slow-by-design (resistant to brute force). |
| **python-jose** | `python-jose[cryptography]` | JWT token generation and verification for stateless authentication. |
| **pdfplumber** | `pdfplumber` | Extracts text from digital (selectable text) PDFs with high fidelity. |
| **pdf2image** | `pdf2image` | Converts scanned PDF pages to images for OCR. Requires Poppler. |
| **pytesseract** | `pytesseract` | Python wrapper for Google's Tesseract OCR engine — the gold standard for open-source OCR. |
| **Pillow** | `Pillow` | Image preprocessing (grayscale conversion, resizing, contrast enhancement) before OCR. |
| **python-docx** | `python-docx` | Extracts text from Word `.docx` files, including text inside tables. |
| **spaCy** | `spacy` | NLP library used as a fallback for Named Entity Recognition (extracting officer names and locations when regex fails). Uses `en_core_web_sm` model. |
| **ReportLab** | `reportlab` | Generates professional PDF reports for case export. Full control over layout, tables, and styling. |
| **python-multipart** | `python-multipart` | Required by FastAPI for file upload (`multipart/form-data`) handling. |

### Frontend

| Technology | Why |
|---|---|
| **HTML5** | Semantic structure. No framework needed for a local tool. |
| **Vanilla CSS** | Full design control. Dark theme with glassmorphism-inspired cards, custom scrollbars, and responsive layout. No Tailwind or Bootstrap. |
| **Vanilla JavaScript** | No React/Vue/Angular. Keeps the frontend zero-dependency (except Chart.js). Direct DOM manipulation via `getElementById` and `fetch()` API calls. |
| **Chart.js** | Lightweight, canvas-based charting library bundled locally (`chart.umd.min.js`). Used for analytics dashboard: bar charts, stacked bar charts. |

### Infrastructure

| Component | Why |
|---|---|
| **MySQL** | Relational database. Chosen for structured case data with relationships between cases, files, and audit logs. LONGTEXT columns for raw extracted text. |
| **Python HTTP Server** | `python -m http.server 5500` — simplest possible static file server for the frontend. No Node.js required. |
| **Tesseract OCR** | Best open-source OCR engine. Must be installed separately on Windows. |
| **Poppler** | PDF rendering library required by `pdf2image` to convert PDF pages to images. Must be installed separately on Windows. |

---

## 4. Project File Structure

```
updated_casedesk/
│
├── .env                         # Environment variables (DB URL, secrets, paths)
├── .gitignore                   # Git exclusions
├── requirements.txt             # Python dependencies
├── start.bat                    # One-click launcher for both servers
├── UPDATED_FEATURES_DOCS.md     # Feature changelog documentation
│
├── backend/
│   ├── main.py                  # FastAPI app entry point, startup migrations, admin seeding
│   ├── database.py              # SQLAlchemy engine, session, Base
│   ├── models.py                # ORM models: Case, CaseFile, User, AuditLog
│   ├── schemas.py               # (Reserved for Pydantic schemas — currently empty)
│   ├── auth.py                  # Password hashing, JWT creation, token verification, role guard
│   ├── validator.py             # Post-extraction validation (empty text, low fields, low OCR, exceptions)
│   ├── test_extract.py          # Manual test script for extraction pipeline
│   │
│   ├── extractor/               # Document processing pipeline
│   │   ├── __init__.py
│   │   ├── detect.py            # File type detection + unified extract_text() dispatcher
│   │   ├── pdf_extractor.py     # Digital PDF (pdfplumber) + scanned PDF (pdf2image + tesseract)
│   │   ├── docx_extractor.py    # Word document text extraction (paragraphs + tables)
│   │   ├── image_extractor.py   # Image OCR with preprocessing (grayscale, resize, contrast)
│   │   ├── field_parser.py      # Regex + spaCy field extraction, R/O pattern, command, PIO numbers
│   │   └── folder_scanner.py    # Bulk folder scanning: case discovery, file collection, processing
│   │
│   ├── routers/                 # FastAPI API routers
│   │   ├── __init__.py
│   │   ├── auth.py              # Login, register, create user, change password, list users
│   │   ├── upload.py            # Single file upload, folder scan (background), scan status, folder picker
│   │   ├── cases.py             # CRUD, search, filter, sort, pagination, download, view files, reprocess
│   │   ├── review.py            # Flagged case list, detail, resolve, escalate
│   │   ├── analytics.py         # Summary stats, cases/year, PIO/year, command/year, type/year
│   │   └── export.py            # PDF report generation with ReportLab
│   │
│   ├── uploads/                 # Uploaded files storage (gitignored)
│   └── exports/                 # Generated PDF reports (gitignored)
│
├── frontend/
│   ├── index.html               # Login page
│   ├── dashboard.html           # Analytics dashboard with charts + user/password management modals
│   ├── cases.html               # Year grid → case list drilldown, search, upload, scan folder
│   ├── case-detail.html         # Single case view: editable fields, document preview, file list, export
│   ├── review.html              # Manual review queue: flagged cases list + detail panel
│   ├── timeline.html            # Chronological case timeline grouped by date
│   ├── analytics.html           # Redirect to dashboard.html
│   │
│   └── assets/
│       ├── style.css            # Complete dark-theme stylesheet (~29 KB)
│       ├── app.js               # Login page logic
│       ├── auth-guard.js        # Auth guard + apiFetch() helper + logout + forced password change
│       ├── dashboard.js         # Dashboard page logic (now analytics-oriented)
│       ├── analytics.js         # Chart.js analytics: 4 charts + drill-down modals
│       ├── cases.js             # Cases page: year grid, case list, search, upload, scan, modals
│       ├── case-detail.js       # Case detail page: load, edit, save, delete, export, preview, reprocess
│       ├── review.js            # Review queue: list flagged cases, resolve, escalate
│       ├── timeline.js          # Timeline page: grouped date display
│       └── chart.umd.min.js    # Chart.js library (bundled locally)
│
└── venv/                        # Python virtual environment (gitignored)
```

---

## 5. Database Schema

The application uses 4 MySQL tables, all defined in `backend/models.py`:

### 5.1 `cases` — Main Case Records

| Column | Type | Description |
|---|---|---|
| `id` | INT (PK, auto) | Unique case identifier |
| `file_name` | TEXT | Name(s) of source file(s) |
| `file_path` | VARCHAR(500) | Path to source file/folder |
| `case_name` | VARCHAR(255) | Folder name used as case identifier |
| `source_folder` | VARCHAR(500) | Original folder path (for dedup/fingerprinting) |
| `officer` | VARCHAR(255) | Extracted officer name |
| `date` | VARCHAR(100) | Extracted incident date |
| `location` | VARCHAR(255) | Extracted location |
| `incident_type` | VARCHAR(255) | Classified type: `Int (Cyber Espionage)`, `Int (Social Media violation)`, `DV / Misc` |
| `complainant` | VARCHAR(255) | Extracted complainant name |
| `suspect` | VARCHAR(255) | Extracted suspect name |
| `evidence` | TEXT | Extracted evidence text |
| `notes` | TEXT | Extracted notes/remarks |
| `raw_text` | LONGTEXT | Full concatenated extracted text from all files |
| `analyst` | VARCHAR(255) | Extracted digital forensic analyst name |
| `investigating_officer` | VARCHAR(255) | Extracted investigating officer name |
| `pertains_service_no` | VARCHAR(255) | Military service/army number the case pertains to |
| `pertains_name` | VARCHAR(255) | Name of the person the case pertains to |
| `pertains_unit` | VARCHAR(255) | Military unit |
| `command` | VARCHAR(100) | Military command (Central, Northern, etc.) |
| `suspected_pio_numbers` | TEXT | Comma-separated suspected PIO phone numbers |
| `suspected_pio_count` | INT | Count of PIO numbers found |
| `date_receiving` / `date_completion` / `date_dispatch` | VARCHAR(100) | Legacy date fields |
| `date_deposition` / `date_issuance` / `date_intimation` / `date_return` | VARCHAR(100) | Case timeline dates |
| `status` | VARCHAR(50) | `open`, `closed`, `pending` |
| `error_flag` | BOOLEAN | Whether case needs manual review |
| `error_reason` | VARCHAR(100) | `EMPTY_TEXT`, `LOW_FIELDS`, `LOW_OCR_CONFIDENCE`, `EXTRACTION_EXCEPTION`, `ESCALATED` |
| `review_note` | TEXT | Reviewer's note |
| `reviewed_by` | VARCHAR(255) | Who reviewed |
| `reviewed_at` | DATETIME | When reviewed |
| `ocr_confidence` | VARCHAR(20) | Average OCR confidence score |
| `uploaded_by` | VARCHAR(100) | Username who uploaded/scanned |
| `file_count` | INT | Number of files in case folder |
| `last_modified` | DATETIME | Latest modification time of case files (used for dedup) |
| `created_at` | DATETIME | Record creation timestamp |
| `updated_at` | DATETIME | Last update timestamp |

### 5.2 `case_files` — Per-File Records

| Column | Type | Description |
|---|---|---|
| `id` | INT (PK, auto) | Unique file record ID |
| `case_id` | INT (FK) | Reference to parent case |
| `file_name` | VARCHAR(255) | Original filename |
| `file_path` | VARCHAR(500) | Path to file on disk |
| `file_type` | VARCHAR(50) | `pdf`, `docx`, `image` |
| `raw_text` | LONGTEXT | Extracted text from this specific file |
| `ocr_confidence` | FLOAT | OCR confidence for this file |
| `extraction_error` | VARCHAR(255) | Error message if extraction failed |
| `created_at` | DATETIME | Record creation timestamp |

### 5.3 `users` — User Accounts

| Column | Type | Description |
|---|---|---|
| `id` | INT (PK, auto) | Unique user ID |
| `username` | VARCHAR(100, unique) | Login username |
| `hashed_password` | VARCHAR(255) | Bcrypt-hashed password |
| `role` | VARCHAR(50) | `admin`, `officer`, `viewer` |
| `must_change_password` | BOOLEAN | Forces password change on next login |
| `created_at` | DATETIME | Account creation timestamp |

### 5.4 `audit_logs` — Activity Audit Trail

| Column | Type | Description |
|---|---|---|
| `id` | INT (PK, auto) | Unique log ID |
| `username` | VARCHAR(100) | Who performed the action |
| `action` | VARCHAR(100) | Action type (e.g., `LOGIN`, `UPLOADED_FILE`, `DELETED_CASE`) |
| `case_id` | INT (nullable) | Related case ID if applicable |
| `details` | VARCHAR(500) | Human-readable description |
| `timestamp` | DATETIME | When the action occurred |

---

## 6. Backend — Detailed Breakdown

### 6.1 Entry Point: `main.py`

- Creates the FastAPI app with title `"CaseDesk API"`.
- Runs `Base.metadata.create_all()` to auto-create tables on startup.
- **Startup event handler** (`startup_db_init`):
  1. Auto-migrates the database schema (adds new columns if missing — handles schema evolution without migration tools like Alembic).
  2. Copies legacy date column values to new columns for backward compatibility.
  3. Seeds a default `admin` account (username: `admin`, password: `admin`) if no admin exists. Flags `must_change_password=True` if the default password is still in use.
  4. Runs `backfill_pertains_fields()` — re-parses raw text for any cases missing the newer metadata fields.
- Configures **CORS middleware** with allowed origins from `.env`.
- Adds **security headers** middleware: Content-Security-Policy, X-Content-Type-Options.
- Registers all 6 routers: auth, upload, cases, review, analytics, export.
- Provides `/` (health message) and `/health` (database connectivity check) endpoints.

### 6.2 Database: `database.py`

- Reads `DB_URL` from `.env` (MySQL connection string with PyMySQL driver).
- Creates SQLAlchemy `engine`, `SessionLocal`, and `Base`.
- Provides `get_db()` dependency for FastAPI's dependency injection.

### 6.3 Auth: `auth.py`

- **Password utilities:** `hash_password()` and `verify_password()` using passlib's bcrypt context.
- **JWT utilities:** `create_access_token()` — encodes username and role into a JWT with configurable expiry.
- **`get_current_user()`** — FastAPI dependency that extracts and validates the JWT from the `Authorization: Bearer <token>` header.
- **`require_role(*roles)`** — factory that returns a dependency checker restricting access to specific roles.

### 6.4 Validator: `validator.py`

Post-extraction quality gate with 4 checks:

1. **EXTRACTION_EXCEPTION** — extraction code crashed.
2. **EMPTY_TEXT** — no text extracted at all.
3. **LOW_OCR_CONFIDENCE** — OCR confidence below 60%.
4. **LOW_FIELDS** — fewer than 3 fields successfully extracted.

If any check fails, `error_flag=True` and the case enters the manual review queue.

### 6.5 Extractor Pipeline

#### `detect.py`
- `detect_file_type()` — returns `pdf`, `docx`, `image`, or `unknown` based on file extension.
- `is_allowed()` — checks if file extension is in `{.pdf, .docx, .jpg, .jpeg, .png}`.
- `extract_text()` — unified dispatcher that calls the appropriate extractor.

#### `pdf_extractor.py`
- **Digital PDFs:** Uses `pdfplumber` to extract selectable text page by page.
- **Scanned PDFs:** Converts pages to images via `pdf2image` (requires Poppler), preprocesses each image (grayscale, upscale if small, contrast enhancement), then runs `pytesseract.image_to_data()` with layout-preserving text reconstruction.
- **Auto-detection:** `is_digital_pdf()` checks if any page has selectable text to decide which method to use.

#### `docx_extractor.py`
- Uses `python-docx` to extract text from paragraphs and tables in Word documents.

#### `image_extractor.py`
- **Preprocessing:** Converts to grayscale, upscales images smaller than 1500px (2× with LANCZOS), enhances contrast by 2×.
- **Dual-pass OCR:** Runs OCR on the full image AND a bottom strip (bottom 22%) to capture timestamps/watermarks. Deduplicates overlapping text.
- **Layout reconstruction:** `reconstruct_text()` reassembles OCR output line-by-line using block/paragraph/line numbers to preserve document structure.

#### `field_parser.py`
The core intelligence of the system. Extracts structured fields from raw text:

- **Regex patterns** for: officer, date, location, incident type, complainant, suspect, evidence, notes.
- **spaCy NER fallback** for officer (PERSON entities) and location (GPE/LOC entities) when regex fails.
- **Command extraction:** Identifies military commands (Central, Northern, Southern, etc.) from keyword patterns.
- **PIO number extraction:** Finds phone numbers following "Suspected PIO" patterns.
- **Case type classification:** Categorizes into `Int (Cyber Espionage)`, `Int (Social Media violation)`, or `DV / Misc`.
- **R/O pattern extraction:** Parses "in R/O [service_no] [name] of [unit]" patterns common in case folder names.
- **Document-aware extraction:** Splits merged text by file markers (`--- filename ---`) and searches specific document types:
  - **Noting sheets** → analyst name
  - **Covering letters** → investigating officer
  - **Hash documents** → deposition date
  - **Return/artefact documents** → issuance and intimation dates
- **`count_extracted_fields()`** — counts how many custom fields (service no, name, unit, analyst, IO, dates) were successfully extracted.

#### `folder_scanner.py`
Handles bulk ingestion from a folder hierarchy:

- **`get_case_folders()`** — discovers case folders from a root path. Supports:
  - Single file input
  - Single case folder input
  - Year-organized directories (e.g., `case_data/2026/Case No-01/`)
  - Container directories with direct case subfolders
  - Automatically ignores loose files in container directories.
- **`collect_files()`** — recursively collects all `.pdf`, `.docx`, `.jpg`, `.jpeg`, `.png` files from a case folder.
- **`process_case_folder()`** — extracts text from every file, merges it, runs field parsing, runs validation, and returns a complete case data dict with per-file records.
- **`get_folder_fingerprint()`** — computes file count + latest modification time for change detection (skip unchanged folders on rescan).

---

## 7. Frontend — Detailed Breakdown

### 7.1 Login Page (`index.html` + `app.js`)

- Simple dark-themed login form.
- Sends credentials as `application/x-www-form-urlencoded` to `POST /auth/login`.
- Stores JWT token, username, role, and `must_change_password` flag in `localStorage`.
- Auto-redirects to dashboard if already logged in.

### 7.2 Auth Guard (`auth-guard.js`)

- Shared across all protected pages.
- Redirects to login if no token in `localStorage`.
- Displays logged-in username in navbar.
- Handles logout (clears `localStorage`).
- Triggers forced password change modal on pages that support it.
- Provides `apiFetch()` helper — wraps `fetch()` with automatic `Authorization: Bearer` header injection and 401 auto-redirect.

### 7.3 Dashboard (`dashboard.html` + `analytics.js`)

- **4 interactive charts** (Chart.js):
  1. **Cases per Year** — bar chart showing case volume over time.
  2. **Suspected PIO Numbers per Year** — bar chart with clickable bars that open a modal listing all PIO phone numbers for that year.
  3. **Cases per Command per Year** — stacked bar chart showing distribution across military commands.
  4. **Cases per Type per Year** — stacked bar chart showing case type distribution.
- Charts dynamically resize based on data volume.
- Clickable chart bars open drill-down modals showing individual case lists.
- **Modals:** Change Password, User Management (admin only), PIO Numbers list, Cases list.

### 7.4 Cases Page (`cases.html` + `cases.js`)

- **Year Grid View** (default): Shows year cards with case counts. Clicking a year drills down.
- **Case List Drilldown:** After selecting a year, shows searchable/sortable case cards.
- **Dual search:** 
  - General search (keywords across officer, location, raw text, etc.) with **hit count display**.
  - Case-specific search (by case number, folder name, or ID).
- **Sorting:** By creation date, deposition date, issuance date, analyst, officer, service number, name, unit, etc.
- **Upload Modal:** Single file upload with status feedback.
- **Scan Folder Modal:** Enter or browse for a folder path → starts background scan → shows live progress (processed/skipped/reprocessed/failed) with auto-polling.
- **Active Scan Banner:** Shows progress bar when a background scan is running.
- **Breadcrumb navigation** between year grid and case list.
- Case cards show: case name, status badge, key metadata (analyst, officer, service no, name, unit, dates), and search hit counts.

### 7.5 Case Detail Page (`case-detail.html` + `case-detail.js`)

- **Editable fields:** Analyst, Investigating Officer, Service No, Name, Unit, Deposition Date, Issuance Date, Intimation Date, Return Date, Status.
- **Document Preview:** Inline PDF/image viewer using `<iframe>` or `<img>` tag with auth token in URL.
- **Raw Text Viewer:** Toggle to view extracted text.
- **Source Files List:** Shows all files in the case with download and view links.
- **Reprocess Fields:** Re-runs the field parser on existing extracted text.
- **Export PDF:** Generates and downloads a formatted PDF report.
- **Delete Case:** With confirmation dialog.
- **Metadata Sidebar:** Case ID, uploaded by, creation date, last updated, error flag, error reason.
- **Save Changes:** Sends PUT request to update case fields.

### 7.6 Review Queue (`review.html` + `review.js`)

- **Split-panel layout:** List of flagged cases on the left, detail panel on the right.
- **Filter by error reason:** EMPTY_TEXT, LOW_FIELDS, LOW_OCR_CONFIDENCE, EXTRACTION_EXCEPTION, ESCALATED.
- **Resolve:** Correct fields manually and clear the error flag.
- **Escalate:** Keep the flag but add an escalation note.

### 7.7 Timeline (`timeline.html` + `timeline.js`)

- Displays all cases grouped by creation date in reverse chronological order.
- Each date group shows case cards with name, officer, location, type, and status.

### 7.8 Styling (`style.css`)

- ~29 KB custom dark-theme stylesheet.
- Color palette: Dark backgrounds (`#0a0e13`, `#111720`, `#1a2129`), blue accents (`#4f9cff`), status colors (green/amber/grey).
- Components: navbar, cards, modals, forms, tables, badges, pagination, tooltips, scrollbars, empty states, scan results, timeline dots.
- Responsive design with media queries for smaller screens.

---

## 8. API Reference

### Authentication (`/auth`)

| Method | Endpoint | Auth | Description |
|---|---|---|---|
| `POST` | `/auth/login` | None | Login with username/password, returns JWT |
| `POST` | `/auth/register` | Admin | Register a new user (admin-only) |
| `POST` | `/auth/create-user` | Admin | Create a new user (admin-only) |
| `GET` | `/auth/users` | Admin | List all registered users |
| `PUT` | `/auth/change-password` | User | Change own password |
| `GET` | `/auth/me` | User | Get current user info |

### Upload (`/upload`)

| Method | Endpoint | Auth | Description |
|---|---|---|---|
| `POST` | `/upload/` | User | Upload a single document file |
| `POST` | `/upload/scan-folder` | User | Start a background folder scan |
| `GET` | `/upload/scan-status` | User | Poll scan progress |
| `POST` | `/upload/select-folder` | User | Open native folder picker dialog (Tkinter) |

### Cases (`/cases`)

| Method | Endpoint | Auth | Description |
|---|---|---|---|
| `GET` | `/cases/` | User | List cases with search, filter, sort, pagination |
| `GET` | `/cases/years` | User | Get available case years with counts |
| `GET` | `/cases/{id}` | User | Get single case detail with files |
| `PUT` | `/cases/{id}` | User | Update case fields |
| `POST` | `/cases/{id}/reprocess` | User | Re-run field parser on case |
| `DELETE` | `/cases/{id}` | User | Delete case and associated files |
| `GET` | `/cases/{id}/download-source` | User | Download the main source file |
| `GET` | `/cases/{id}/view-source` | User | View the main source file inline |
| `GET` | `/cases/files/{file_id}/download` | User | Download a specific case file |
| `GET` | `/cases/files/{file_id}/view` | User | View a specific case file inline |
| `GET` | `/cases/timeline/all` | User | Get all cases grouped by date for timeline |

### Review (`/review`)

| Method | Endpoint | Auth | Description |
|---|---|---|---|
| `GET` | `/review/` | User | List flagged cases (with optional error_reason filter) |
| `GET` | `/review/{id}` | User | Get flagged case detail |
| `PUT` | `/review/{id}/resolve` | User | Resolve flagged case (correct fields, clear flag) |
| `PUT` | `/review/{id}/escalate` | User | Escalate flagged case (keep flag, add note) |

### Analytics (`/analytics`)

| Method | Endpoint | Auth | Description |
|---|---|---|---|
| `GET` | `/analytics/summary` | User | Full analytics data: counts, per-year, per-command, per-type |
| `GET` | `/analytics/pio-numbers?year=YYYY` | User | List PIO phone numbers for a specific year |

### Export (`/export`)

| Method | Endpoint | Auth | Description |
|---|---|---|---|
| `GET` | `/export/{case_id}` | User | Generate and download PDF report for a case |

---

## 9. Features

### Core Features

1. **Multi-format Document Ingestion** — PDF (digital + scanned), DOCX, JPG/JPEG/PNG.
2. **Automatic Text Extraction** — pdfplumber for digital PDFs, Tesseract OCR for scanned documents, python-docx for Word files.
3. **Intelligent Field Parsing** — Regex + spaCy NER automatically identifies 20+ structured fields from unstructured text.
4. **Bulk Folder Scanning** — Point to a root folder, and the system recursively discovers and processes all case subfolders with multi-threaded processing.
5. **Change Detection** — Folder scans skip unchanged cases (based on file count + modification time fingerprinting) and reprocess changed ones.
6. **Automatic Backfill** — On startup, re-parses existing cases missing newer metadata fields.
7. **Post-Extraction Validation** — Automatically flags cases with quality issues for manual review.
8. **Search with Hit Counts** — Full-text search across all fields with relevance ranking (cases sorted by hit count, showing "X hits across Y cases").
9. **Case-specific Search** — Search by case number, folder name, or case ID.
10. **Year-Based Organization** — Cases grouped by year, extracted from folder paths, case names, or dates.
11. **Inline Document Preview** — View PDFs and images directly in the browser.
12. **Editable Case Fields** — Manually correct or update any extracted field.
13. **Reprocess Fields** — Re-run the parser on existing text without re-extracting.
14. **PDF Report Export** — Generate professional A4 PDF reports with case overview, custom fields, evidence, notes, source files, and review status.
15. **Case Timeline** — Chronological view of all cases grouped by creation date.

### Analytics Features

16. **Cases per Year Chart** — Bar chart showing case volume trends.
17. **Suspected PIO Numbers per Year** — Track phone numbers identified in documents with drill-down to individual numbers.
18. **Cases per Command per Year** — Stacked bar chart for command distribution analysis.
19. **Cases per Type per Year** — Stacked bar chart for case type distribution.
20. **Drill-down Modals** — Click any chart bar to see the underlying case list.

### Review & Quality Features

21. **Manual Review Queue** — Split-panel interface for reviewing flagged cases.
22. **Resolve/Escalate Workflow** — Correct fields and clear flags, or escalate with notes.
23. **Error Categorization** — Specific error reasons: EMPTY_TEXT, LOW_FIELDS, LOW_OCR_CONFIDENCE, EXTRACTION_EXCEPTION, ESCALATED.
24. **Matched File Highlighting** — Search results show which specific files contain matches and how many hits.

### Security & Admin Features

25. **JWT Authentication** — Stateless token-based auth with configurable expiry.
26. **Bcrypt Password Hashing** — Secure password storage.
27. **Role-Based Access Control** — Admin, Officer, Viewer roles.
28. **Auto Admin Seeding** — Default admin account created on first run.
29. **Forced Password Change** — Default password triggers mandatory change modal.
30. **User Management** — Admin can create/list users with role assignment.
31. **Audit Logging** — Every significant action (login, upload, delete, resolve, export, etc.) is logged.
32. **CORS Configuration** — Configurable allowed origins.
33. **Security Headers** — CSP, X-Content-Type-Options.
34. **Path Traversal Protection** — File download/view endpoints validate paths against allowed directories.

### UX Features

35. **Native Folder Picker** — Tkinter-based OS dialog for selecting scan folders.
36. **Live Scan Progress** — Real-time progress polling with processed/skipped/reprocessed/failed counts.
37. **Active Scan Banner** — Persistent notification when a scan is running.
38. **Pagination** — Configurable page size with navigation controls.
39. **Dark Theme** — Full custom dark UI with blue accents.
40. **One-Click Launcher** — `start.bat` launches both servers and opens browser.

---

## 10. Authentication & Security

### Authentication Flow

```
1. User submits username + password to POST /auth/login
2. Backend verifies credentials against bcrypt hash in users table
3. Backend creates JWT containing: { sub: username, role: role, exp: timestamp }
4. JWT returned to frontend, stored in localStorage
5. All subsequent API calls include header: Authorization: Bearer <token>
6. Backend validates JWT on every protected endpoint via get_current_user() dependency
7. If token is expired or invalid → 401 response → frontend clears storage → redirect to login
```

### Password Security

- Passwords hashed with bcrypt (via passlib) — computationally expensive to crack.
- Minimum 6-character password requirement.
- Default admin password (`admin`) flagged for mandatory change via `must_change_password` field.

### Role System

| Role | Permissions |
|---|---|
| `admin` | Full access + user management (create users, list users) |
| `officer` | View, search, upload, edit, review, export cases |
| `viewer` | View and search cases only |

### Security Headers

- **Content-Security-Policy:** Restricts script sources, connection targets, and frame ancestors.
- **X-Content-Type-Options:** `nosniff` — prevents MIME-type sniffing.

### File Access Security

- File download and view endpoints use `get_safe_file_path()` which:
  - Resolves absolute paths.
  - Checks file exists on disk.
  - Validates the path is within allowed directories (upload dir, source folder, or project base).
  - Normalizes paths for Windows drive letter/case matching.
  - Blocks path traversal attacks.

---

## 11. Document Extraction Pipeline

```
Input Document
      │
      ▼
┌──────────────┐
│  detect.py   │ ← Determines file type (pdf/docx/image)
└──────┬───────┘
       │
       ├── PDF ──────────────────────┐
       │                             ▼
       │               ┌──────────────────────┐
       │               │  is_digital_pdf()?   │
       │               └──────┬───────────────┘
       │                      │
       │              Yes ────┼──── No
       │               │      │      │
       │               ▼      │      ▼
       │         pdfplumber   │   pdf2image → preprocess → tesseract OCR
       │           (text)     │   (images → grayscale → upscale → contrast → OCR)
       │               │      │      │
       │               ▼      │      ▼
       │          (text, None) │  (text, confidence)
       │                      │
       ├── DOCX ──────────────┤
       │                      │
       │         python-docx  │
       │    (paragraphs +     │
       │     tables)          │
       │         │            │
       │         ▼            │
       │    (text, None)      │
       │                      │
       ├── Image ─────────────┤
       │                      │
       │    Pillow preprocess  │
       │    → Full image OCR   │
       │    → Bottom strip OCR │
       │    → Deduplicate      │
       │         │            │
       │         ▼            │
       │    (text, confidence) │
       │                      │
       └──────────────────────┘
                  │
                  ▼
         ┌────────────────┐
         │  field_parser   │ ← Regex patterns for each field
         │  parse_fields() │ ← spaCy NER fallback for officer/location
         │                 │ ← R/O pattern for service_no/name/unit
         │                 │ ← Command classification
         │                 │ ← PIO number extraction
         │                 │ ← Case type classification
         │                 │ ← Document-aware (noting sheet, covering letter, hash doc)
         └────────┬───────┘
                  │
                  ▼
         ┌────────────────┐
         │  validator.py   │ ← Quality gate: empty text? low fields? low OCR? exceptions?
         └────────┬───────┘
                  │
                  ▼
         Store in MySQL (cases + case_files tables)
         If error_flag=True → appears in Review Queue
```

---

## 12. Setup & Reproduction Guide

### Prerequisites

1. **Python 3.10+** — [python.org](https://www.python.org/downloads/)
2. **MySQL Server** — [mysql.com](https://dev.mysql.com/downloads/mysql/) (or MariaDB)
3. **Tesseract OCR** — [github.com/tesseract-ocr](https://github.com/UB-Mannheim/tesseract/wiki)
   - Install to `C:\Program Files\Tesseract-OCR\` (or update `.env`)
4. **Poppler** — [github.com/oschwartz10612/poppler-windows](https://github.com/oschwartz10612/poppler-windows/releases)
   - Extract to `C:\poppler-XX.XX.X\` (or update `.env`)
5. **Git** (optional, for cloning)

### Step-by-Step Setup

#### 1. Clone or Copy the Project

```bash
git clone <repository-url> updated_casedesk
cd updated_casedesk
```

#### 2. Create Python Virtual Environment

```bash
python -m venv venv
```

#### 3. Activate Virtual Environment

```bash
# Windows (CMD)
venv\Scripts\activate

# Windows (PowerShell)
.\venv\Scripts\Activate.ps1
```

#### 4. Install Python Dependencies

```bash
pip install -r requirements.txt
```

#### 5. Download spaCy Language Model

```bash
python -m spacy download en_core_web_sm
```

#### 6. Create MySQL Database

```sql
CREATE DATABASE updated_casedesk CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
```

#### 7. Configure Environment Variables

Create or edit the `.env` file in the project root:

```env
DB_URL=mysql+pymysql://root:YOUR_MYSQL_PASSWORD@localhost:3306/updated_casedesk
SECRET_KEY=your_random_secret_key_here_minimum_32_chars
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=60
TESSERACT_PATH=C:\Program Files\Tesseract-OCR\tesseract.exe
POPPLER_PATH=C:\poppler-XX.XX.X\Library\bin
ALLOWED_ORIGINS=http://127.0.0.1:5500,http://localhost:5500,http://127.0.0.1:8000,http://localhost:8000
```

> **Important:** URL-encode special characters in the MySQL password (e.g., `@` → `%40`).

#### 8. Start the Application

**Option A: One-click launcher**

```bash
start.bat
```

This starts both servers and opens the browser automatically.

**Option B: Manual start (two separate terminals)**

Terminal 1 — Backend:
```bash
cd backend
..\venv\Scripts\activate
uvicorn main:app --reload --port 8000
```

Terminal 2 — Frontend:
```bash
cd frontend
..\venv\Scripts\activate
python -m http.server 5500
```

#### 9. Open in Browser

Navigate to `http://127.0.0.1:5500`

#### 10. Login

Default credentials (auto-created on first run):
- **Username:** `admin`
- **Password:** `admin`

You will be prompted to change the default password on first login.

---

## 13. Environment Variables

| Variable | Description | Example |
|---|---|---|
| `DB_URL` | MySQL connection string (SQLAlchemy format) | `mysql+pymysql://root:pass@localhost:3306/updated_casedesk` |
| `SECRET_KEY` | JWT signing key (keep secret, minimum 32 chars) | `9f8e7d6c5b4a3f2e1d9c8b7a...` |
| `ALGORITHM` | JWT algorithm | `HS256` |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | Token validity duration in minutes | `60` |
| `TESSERACT_PATH` | Absolute path to `tesseract.exe` | `C:\Program Files\Tesseract-OCR\tesseract.exe` |
| `POPPLER_PATH` | Absolute path to Poppler `bin` directory | `C:\poppler-26.02.0\Library\bin` |
| `ALLOWED_ORIGINS` | Comma-separated CORS origins | `http://127.0.0.1:5500,http://localhost:5500,...` |

---

## 14. Running the Application

### Development Mode

```bash
# Backend (with hot-reload)
cd backend
uvicorn main:app --reload --port 8000

# Frontend (separate terminal)
cd frontend
python -m http.server 5500
```

### API Documentation (Auto-Generated)

FastAPI automatically generates interactive API docs:
- **Swagger UI:** http://127.0.0.1:8000/docs
- **ReDoc:** http://127.0.0.1:8000/redoc

### Health Check

```bash
curl http://127.0.0.1:8000/health
# Response: {"status":"ok","database":"connected"}
```

### Running Extraction Tests

```bash
cd backend
python test_extract.py
```

This runs 5 test cases validating the extraction and validation pipeline.

---

## 15. Troubleshooting

| Issue | Solution |
|---|---|
| `ModuleNotFoundError: No module named 'pymysql'` | Activate venv and run `pip install -r requirements.txt` |
| `Tesseract not found` | Install Tesseract OCR and update `TESSERACT_PATH` in `.env` |
| `pdf2image: Unable to get page count` | Install Poppler and update `POPPLER_PATH` in `.env` |
| `Access denied for user 'root'@'localhost'` | Check MySQL credentials in `DB_URL`. URL-encode special characters. |
| `CORS error` in browser console | Ensure frontend URL is listed in `ALLOWED_ORIGINS` in `.env` |
| `401 Unauthorized` on every API call | Token expired. Clear localStorage and re-login. |
| Scanned PDFs produce garbage text | Ensure Tesseract is properly installed. Check image quality. |
| spaCy model not found | Run `python -m spacy download en_core_web_sm` |
| `tkinter` folder picker doesn't open | Tkinter may not be installed. Use the manual path input instead. |
| Port already in use | Change port: `uvicorn main:app --port 8001` or `python -m http.server 5501` and update `ALLOWED_ORIGINS` |
| Database tables missing columns | Restart the backend — `startup_db_init` auto-migrates schema. |

---

*This documentation was auto-generated from a complete analysis of the CaseDesk codebase. Last updated: July 2026.*
