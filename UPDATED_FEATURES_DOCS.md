# CaseDesk — Added Features Documentation

This document describes the two features implemented in this update, including details of what was added, where it was implemented, and why the changes were made.

---

## 1. Search Hit Counts

### What was added
- A python helper `count_hits` in the cases router to count occurrences of a search term case-insensitively across searchable Case fields: `raw_text`, `officer`, `location`, `complainant`, `suspect`, `case_name`, `incident_type`, `notes`, and `evidence`.
- A modified `GET /cases` endpoint that calculates:
  - `total_hits`: The sum of all matching hits across all cases matching the query.
  - `hit_count`: The individual hit count for each specific case card.
- A search hit stats subtitle on the frontend dashboard (e.g., `"15 hits across 3 cases"` instead of `"3 cases found"`).
- Dynamic hit count badges displayed next to the status badge on the case cards.

### Why it was added
- **Enhanced Search Relevance**: Standard search filters only tell you if a case matches, but doesn't tell you how frequently or heavily the search term occurs. Displaying hit counts allows officers to immediately identify the most relevant files.

### Files Modified
- [backend/routers/cases.py](file:///e:/updated_casedesk/backend/routers/cases.py): Added counting helper, calculated metrics, and returned them in JSON response.
- [frontend/assets/dashboard.js](file:///e:/updated_casedesk/frontend/assets/dashboard.js): Handled hit statistics in UI logic and rendered case hit counts dynamically.
- [frontend/assets/style.css](file:///e:/updated_casedesk/frontend/assets/style.css): Styled the new `.badge-hits` pill and organized multiple badges into a vertical stack (`.case-card-badges`).

---

## 2. Auto-Admin Account & User Management

### What was added
- **Automatic Seeding**: A startup event handler that runs when the FastAPI application starts, checks if an `admin` user exists, and seeds it with default credentials (`username: admin`, `password: admin`) if not.
- **Change Password**: An endpoint allowing any logged-in user to change their own password by verifying their current password first.
- **Admin User Management**: Admin-only endpoints to register/create new users and list all registered users.
- **Admin UI Panels**:
  - A **User Management** modal for admins to list existing accounts and create new users with roles (`admin`, `officer`, `viewer`).
  - A **Change Password** modal for any logged-in user.
  - Role-based visibility for the navbar "User Management" option.

### Why it was added
- **Local Sandbox Setup**: Because this application is designed to run locally, it needs to work out-of-the-box on a new system. Auto-creating the default admin account eliminates the need for manual SQL seeding.
- **Access Control & Security**: Restricted the open `/auth/register` route to ensure random visitors cannot sign up or elevate their privileges. Only admins can register new users.

### Files Modified
- [backend/main.py](file:///e:/updated_casedesk/backend/main.py): Added `@app.on_event("startup")` user seeding logic.
- [backend/routers/auth.py](file:///e:/updated_casedesk/backend/routers/auth.py): Added user creation, change-password, and listing endpoints secured with role checks.
- [frontend/dashboard.html](file:///e:/updated_casedesk/frontend/dashboard.html): Added navbar control items and HTML forms/modals for changing passwords and managing users.
- [frontend/assets/dashboard.js](file:///e:/updated_casedesk/frontend/assets/dashboard.js): Handled modal actions, network request logic, and role-based visibility.
- [frontend/assets/style.css](file:///e:/updated_casedesk/frontend/assets/style.css): Styled navigation buttons and user management data table.
