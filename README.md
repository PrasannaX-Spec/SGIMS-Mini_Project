# Security Agency Management and Monitoring System (SGIMS)

A modern, enterprise-grade multi-tenant operations ERP and monitoring platform built for security agencies (Karnataka, India context), scaling from 200 to 500+ active security guards across distributed client sites.

---

## Current Status: Modules 1–7 Completed (100% Tested)

| Module | Title | Status | Tests | Core Capabilities |
|---|---|---|---|---|
| **Module 1** | Foundation | Completed | 17/17 | Authentication, RBAC, Scope Grants, Device Registration, Consent Records, Audit Logging, In-App Notifications |
| **Module 2** | Master Data | Completed | 6/6 | Client Organizations, Security Sites, Circular & Polygon Geofences, Guard Ranks, Shift Types, Commercial Rates |
| **Module 3** | Guard Management | Completed | 5/5 | Guard Onboarding, PSARA Verification, KYC Documents, ID Badges, Uniform Issues, Disciplinary Lifecycle |
| **Module 4** | Service Requests & Quotations | Completed | 4/4 | Client Service Inquiries, Post Requirements, Minimum Wage Cost Sheets (Karnataka VDA), Quotation PDF Approvals |
| **Module 5** | Deployment & Roster | Completed | 7/7 | Post Slots, Monthly & Weekly Shift Rosters, Rest Day / Overtime Compliance, Replacement Workflows |
| **Module 6** | Attendance & Verification | Completed | 6/6 | Geofenced In-App Check-In/Out, GPS + Live Photo Evidence, Offline Sync, Anomaly Flags, Attendance Approvals & Period Closures |
| **Module 7** | Live Monitoring | Completed | 8/8 | Duty-Time Location Tracking, SVG Radar Map, Decoupled Statuses, Debounced Geofence Alarms, Escalated Alerts, Supervisor Safety Pings, Breadcrumb Trail Replay |

**Total Regression Test Suite: 53 / 53 Passing (100%)**

---

## Technology Stack

- **Backend:** Python 3.11+, Django 6.1, Django REST Framework 3.18, SimpleJWT, Argon2 Password Hashing
- **Database:** PostgreSQL 14+ with custom `security_erp` schema and PostGIS / Haversine geofence functions
- **Frontend:** React 19, Vite 8, Tailwind CSS v4, Lucide React Icons, Axios
- **Architecture:** Unmanaged Django ORM models mapped directly to audited, relational SQL schema files

---

## Quick Start Guide

For full instructions, refer to the detailed [SETUP_GUIDE.md](./SETUP_GUIDE.md).

### 1. Prerequisites
- **Python 3.11+** installed
- **Node.js 18+ & npm** installed
- **PostgreSQL 14+** running locally on port `5432`

### 2. Database Setup
In PostgreSQL (using `psql` or pgAdmin), create the database:
```sql
CREATE DATABASE security_agency_erp;
```

### 3. Backend Setup
```bash
# Navigate to backend
cd backend

# Create and activate virtual environment
python -m venv ..\venv
..\venv\Scripts\activate   # On Windows (PowerShell: ..\venv\Scripts\Activate.ps1)
# source ../venv/bin/activate  # On Linux / macOS

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env with your PostgreSQL password (e.g. DB_PASSWORD=your_password)

# Run one-shot database initializer (creates schema, tables & seeds default admin)
python init_db.py

# Run full test suite (53 tests across Modules 1-7)
python manage.py test
```

### 4. Frontend Setup
```bash
# In a separate terminal, navigate to frontend
cd frontend

# Install npm packages
npm install

# Start Vite development server
npm run dev
```

### 5. Access the Platform
- **Frontend Web Console:** [http://127.0.0.1:5173/](http://127.0.0.1:5173/)
- **Backend API:** [http://127.0.0.1:8000/api/](http://127.0.0.1:8000/api/)
- **Default Admin Account:**
  - **Email:** `admin@securityagency.local`
  - **Password:** `AdminPass123!`

---

## Directory Structure

```
SGIMS_5/
├── backend/                         # Django REST Framework Backend
│   ├── attendance/                  # Module 6: Attendance & Evidence
│   ├── config/                      # Django Settings & URL routing
│   ├── deployment_roster/           # Module 5: Post Slots & Roster Planning
│   ├── foundation/                  # Module 1: Auth, Audit, Users, Consents
│   ├── guard_management/           # Module 3: Guard Profiles & Verification
│   ├── live_monitoring/            # Module 7: Live Telemetry, Radar Map & Alerts
│   ├── master_data/                 # Module 2: Clients, Sites & Geofences
│   ├── service_quotation/           # Module 4: Service Requests & Cost Sheets
│   ├── init_db.py                   # Automated Database Setup & Seeder Script
│   ├── manage.py
│   ├── requirements.txt             # Python Package Dependencies
│   └── .env.example                 # Environment Variables Template
├── frontend/                        # React 19 + Vite Frontend
│   ├── src/
│   │   ├── api.js                   # Unified Axios API Client for all modules
│   │   ├── App.jsx                  # Main Navigation & Tab Manager
│   │   ├── components/              # Shared Sidebar, Navbar, Modals
│   │   └── screens/                 # Operational Screen Consoles (Modules 1–7)
│   ├── package.json
│   └── vite.config.js
├── security_agency_erp_schema_postgresql.sql # Base SQL Schema & Extensions
├── module1_foundation_schema.sql             # Module 1 Database Schema
├── module2_master_data_schema.sql            # Module 2 Database Schema
├── module3_guard_management_schema.sql       # Module 3 Database Schema
├── module4_service_quotation_schema.sql      # Module 4 Database Schema
├── module5_deployment_roster_schema.sql      # Module 5 Database Schema
├── module6_attendance_schema.sql             # Module 6 Database Schema
├── module7_live_monitoring_schema.sql        # Module 7 Database Schema
├── README.md                                 # High-level Documentation
└── SETUP_GUIDE.md                            # Comprehensive Developer Setup Guide
```

---

## Upcoming Modules Roadmap

1. **Module 8:** Incidents & Occurrence Reporting
2. **Module 9:** Patrol & Tour Verification
3. **Module 10:** Client Portal & Visibility
4. **Module 11:** Billing & Client Invoicing
5. **Module 12:** Guard Mobile Application Shell
6. **Module 13:** Operational Analytics & Reports
7. **Module 14:** Payroll & Statutory Deductions (EPF, ESI, PT)

---

## License & Team
Developed for Security Agency Operations & Monitoring Management.

