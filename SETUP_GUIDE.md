# Security Agency ERP — Developer Setup & Handover Guide

This document provides complete, step-by-step instructions for cloning, setting up, running, testing, and continuing development on the **Security Agency Management and Monitoring System (SGIMS)**.

---

## 1. System Requirements & Prerequisites

Before starting, ensure your machine has the following tools installed and available on your system `PATH`:

| Tool | Minimum Version | Recommended Version | Verification Command |
|---|---|---|---|
| **Python** | 3.11.x | 3.12.x | `python --version` |
| **Node.js** | 18.x | 20.x+ (LTS) | `node -v` |
| **npm** | 9.x | 10.x+ | `npm -v` |
| **PostgreSQL** | 14.x | 16.x | `psql --version` |
| **Git** | 2.30+ | Latest | `git --version` |

---

## 2. Repository Cloning & Git Setup

If you are cloning this repository from GitHub:

```bash
git clone <repository_url> SGIMS_5
cd SGIMS_5
```

### Git Ignore Notes
The repository root contains a configured `.gitignore` that prevents:
- Virtual environments (`venv/`, `.venv/`)
- Backend environment secret files (`backend/.env`)
- Frontend dependency and build artifacts (`node_modules/`, `dist/`)
- Python bytecode and cache files (`__pycache__/`, `*.pyc`)

---

## 3. Database Setup (PostgreSQL)

The ERP stores all data in PostgreSQL using a dedicated schema named `security_erp`.

### Step 3.1: Create the Database
Open your terminal (or pgAdmin) and connect to your local PostgreSQL instance:

```bash
psql -U postgres -h 127.0.0.1
```

Inside the PostgreSQL prompt, create the database:

```sql
CREATE DATABASE security_agency_erp;
\q
```

*(Note: You do not need to create tables or schemas manually; the Python initialization script will do this automatically in Step 4.4).*

---

## 4. Backend Setup (Django REST Framework)

### Step 4.1: Create & Activate Virtual Environment

From the project root:

**On Windows (PowerShell):**
```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
```
*(If you encounter a PowerShell script execution policy error, run: `Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass`)*

**On Linux / macOS:**
```bash
python3 -m venv venv
source venv/bin/activate
```

---

### Step 4.2: Install Backend Dependencies

With the virtual environment activated:

```bash
cd backend
pip install --upgrade pip
pip install -r requirements.txt
```

---

### Step 4.3: Configure Environment Variables

Create a `.env` file in the `backend/` directory by copying the provided example:

**On Windows (PowerShell):**
```powershell
Copy-Item .env.example .env
```

**On Linux / macOS:**
```bash
cp .env.example .env
```

Open `backend/.env` in your text editor and update the database credentials to match your local PostgreSQL setup:

```env
# Database Configuration (PostgreSQL)
DB_NAME=security_agency_erp
DB_USER=postgres
DB_PASSWORD=your_actual_postgres_password   # <-- Change this!
DB_HOST=127.0.0.1
DB_PORT=5432
DB_SCHEMA=security_erp

# Secret Key & Debug Mode
DEBUG=True
SECRET_KEY=your-custom-django-secret-key-here
ALLOWED_HOSTS=localhost,127.0.0.1

# CORS Settings
CORS_ALLOWED_ORIGINS=http://localhost:5173,http://127.0.0.1:5173,http://localhost:3000

# Timezone & Metadata
TIME_ZONE=Asia/Kolkata
AGENCY_DOMAIN=localhost:8000
AGENCY_NAME=Security Agency Management System
```

---

### Step 4.4: Initialize Database & Seed Default Admin

Run the automated initialization script from inside the `backend/` directory:

```bash
python init_db.py
```

This single command will:
1. Connect to PostgreSQL.
2. Drop and recreate the `security_erp` schema safely.
3. Sequentially apply all 8 module SQL schemas in order:
   - `security_agency_erp_schema_postgresql.sql` (Base types, domains & schema)
   - `module1_foundation_schema.sql` (Auth, Users, Scopes, Consents, Devices)
   - `module2_master_data_schema.sql` (Clients, Sites, Geofences, Rates)
   - `module3_guard_management_schema.sql` (Guards, Verifications, Badges)
   - `module4_service_quotation_schema.sql` (Service Requests, Cost Sheets)
   - `module5_deployment_roster_schema.sql` (Shifts, Slots, Rosters)
   - `module6_attendance_schema.sql` (Attendance, Evidence, Geofence)
   - `module7_live_monitoring_schema.sql` (Telemetry, Radar, Alerts, Trails)
4. Initialize system configuration settings and notification categories.
5. Seed the default Organization (`Karnataka Security Services Ltd`) and default Administrator account.

---

### Step 4.5: Run Backend Automated Tests

Verify that all 53 automated tests across Modules 1 through 7 pass cleanly:

```bash
python manage.py test
```

Expected output:
```text
Ran 53 tests in ~14s
OK
```

---

### Step 4.6: Start the Django Development Server

```bash
python manage.py runserver 127.0.0.1:8000
```

The Django API is now live at: `http://127.0.0.1:8000/api/`

---

## 5. Frontend Setup (React 19 + Vite)

Open a **new terminal window** (keep the Django server running in the first terminal).

### Step 5.1: Install Node Dependencies

```bash
cd SGIMS_5/frontend
npm install
```

### Step 5.2: Start the Vite Development Server

```bash
npm run dev
```

The React Web Console is now accessible at: `http://127.0.0.1:5173/`

---

## 6. Default Login Credentials

Use the pre-seeded credentials to sign in to the web console:

| Role | Email | Password | Permissions |
|---|---|---|---|
| **Admin** | `admin@securityagency.local` | `AdminPass123!` | Organization-wide access to all modules, configurations, approvals, and audits |

---

## 7. Architecture & Developer Guidelines (How to Continue)

If you are continuing development (e.g. building **Module 8: Incidents & Occurrence Reporting**), follow these architectural rules:

### 1. Unmanaged Relational SQL Pattern
- Django models in this project use `managed = False`.
- Tables are defined authoritatively in relational PostgreSQL SQL scripts located at the repository root.
- Table names are prefixed with the schema:
  ```python
  class Meta:
      managed = False
      db_table = 'security_erp"."incident_reports'
  ```

### 2. Cross-Module Foreign Keys
- When creating relationships across modules, avoid assigning model instances directly if they belong to different apps (e.g. `foundation.models.Company` vs `master_data.models.Company`).
- Always assign by ID (e.g., `company_id=request.user.company_id` or `site_id=...`).

### 3. User Active Status
- The custom `User` model uses a string status field (`status = 'ACTIVE'`), **not** Django's default boolean `is_active`.
- Query active users with `User.objects.filter(status='ACTIVE')`.

### 4. RBAC & Multi-Tenancy Scope Checks
- Every API view must declare:
  ```python
  permission_classes = [IsAuthenticated, HasCapabilityAndScope]
  required_capability = 'incidents.create'  # or appropriate capability
  ```
- Always filter querysets by the request user's company:
  ```python
  company_id = request.user.company_id
  qs = IncidentReport.objects.filter(company_id=company_id)
  ```
- For **Supervisors**, filter by their assigned sites via `SiteSupervisorAssignment`:
  ```python
  if request.user.role == 'SUPERVISOR':
      assigned_sites = SiteSupervisorAssignment.objects.filter(
          supervisor_user_id=request.user.user_id, is_active=True
      ).values_list('site_id', flat=True)
      qs = qs.filter(site_id__in=assigned_sites)
  ```

### 5. Automated Testing Convention
- Every new module must include a `tests.py` file with test cases verifying each Acceptance Criteria (AC) from the PRD.
- Register any new module's SQL script in `backend/foundation/test_runner.py` under `PostgreSQLSchemaTestRunner.setup_databases()` so that test databases automatically execute the new schema.

### 6. Frontend UI Standards
- Built with **React 19**, **Tailwind CSS v4**, and **Lucide React** icons.
- Buttons use clean rectangular geometry with `rounded-md` (never use pill-shaped buttons).
- Color coding standards:
  - Emerald (`emerald-50`, `emerald-600`): Approved, On-duty, Present, Resolved.
  - Amber/Orange (`amber-50`, `amber-600`): Outside Geofence, Pending Approval, Warnings.
  - Rose/Red (`rose-50`, `rose-600`): Critical Alerts, No Contact, Rejected, Breaches.
  - Slate/Gray (`slate-900`, `gray-100`): Neutral cards, headers, tables.

---

## 8. Troubleshooting FAQ

### Q: `init_db.py` throws `psycopg2.OperationalError: connection to server at "127.0.0.1" failed`
**Fix:** Verify that PostgreSQL service is running on your computer. On Windows, check Windows Services (`services.msc` -> `postgresql-x64-16`). Check port `5432` and verify the `DB_PASSWORD` in `backend/.env`.

### Q: `python manage.py test` fails with `relation does not exist`
**Fix:** Ensure that `backend/foundation/test_runner.py` is referenced in `backend/config/settings.py` as:
`TEST_RUNNER = 'foundation.test_runner.PostgreSQLSchemaTestRunner'`.

### Q: Vite displays `AxiosError: Network Error` in browser
**Fix:** Ensure the Django server is running in terminal 1 on port 8000 (`http://127.0.0.1:8000`). Check `frontend/src/api.js` to ensure the base URL is `http://127.0.0.1:8000/api`.

---

## 9. Pushing to GitHub (Ready Command List)

To push this complete codebase to a new GitHub repository:

```bash
# Initialize git repository
git init

# Add all files (respects root .gitignore)
git add .

# Create initial commit
git commit -m "feat: complete Modules 1-7 (Foundation, Master Data, Guards, Quotations, Roster, Attendance, Live Monitoring)"

# Set default branch to main
git branch -M main

# Add remote and push (replace with your repo URL)
git remote add origin https://github.com/<your-username>/<your-repo-name>.git
git push -u origin main
```

Everything is tested, self-contained, and ready for your teammate to continue with Module 8!

