"""
Database Initialization Script for Security Agency ERP.
Executes all ERP module schema scripts in order on the configured database.

Usage:
    cd backend
    python init_db.py
"""
import os
import sys
import django
from pathlib import Path

# Setup Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from django.db import connection, transaction

def initialize_database():
    base_dir = Path(__file__).resolve().parent.parent

    schemas = [
        ("Base Schema & Schema Setup", base_dir / "security_agency_erp_schema_postgresql.sql"),
        ("Module 1: Foundation Schema", base_dir / "module1_foundation_schema.sql"),
        ("Module 2: Master Data Schema", base_dir / "module2_master_data_schema.sql"),
        ("Module 3: Guard Management Schema", base_dir / "module3_guard_management_schema.sql"),
        ("Module 4: Service Quotation Schema", base_dir / "module4_service_quotation_schema.sql"),
        ("Module 5: Deployment & Roster Schema", base_dir / "module5_deployment_roster_schema.sql"),
        ("Module 6: Attendance Schema", base_dir / "module6_attendance_schema.sql"),
        ("Module 7: Live Monitoring Schema", base_dir / "module7_live_monitoring_schema.sql"),
        ("Module 8: Incident & Request Schema", base_dir / "module8_incident_request_schema.sql"),
        ("Module 9: Panic & Escalation Schema", base_dir / "module9_panic_escalation_schema.sql"),
        ("Module 10: Client Portal Schema", base_dir / "module10_client_portal_schema.sql"),
        ("Module 11: Billing & Invoices Schema", base_dir / "module11_billing_invoices_schema.sql"),
        ("Module 12: Armed Guard & Weapons Register Schema", base_dir / "module12_weapons_register_schema.sql"),
        ("Module 13: Reports & Dashboards Schema", base_dir / "module13_reports_dashboards_schema.sql"),
    ]

    print("==================================================")
    print("Security Agency ERP - Database Initializer")
    print("==================================================")
    print(f"Target Database: {connection.settings_dict.get('NAME')}")
    print(f"Target Host:     {connection.settings_dict.get('HOST')}:{connection.settings_dict.get('PORT')}")
    print(f"Target User:     {connection.settings_dict.get('USER')}")
    print("--------------------------------------------------")

    with connection.cursor() as cursor:
        if '--reset' in sys.argv:
            print("Resetting schema 'security_erp' (CASCADE)...", end="", flush=True)
            cursor.execute("DROP SCHEMA IF EXISTS security_erp CASCADE; CREATE SCHEMA security_erp;")
            print(" [OK]")

        for name, file_path in schemas:
            if not file_path.exists():
                print(f"[!] Warning: File not found: {file_path.name}")
                continue

            print(f"Applying: {name} ({file_path.name})...", end="", flush=True)
            with open(file_path, "r", encoding="utf-8") as f:
                sql_content = f.read()
                try:
                    with transaction.atomic():
                        cursor.execute(sql_content)
                    print(" [OK]")
                except Exception as ex:
                    if "already exists" in str(ex):
                        print(" [Exists - OK]")
                    else:
                        raise ex

    print("==================================================")
    print("All ERP database schemas applied successfully!")
    print("--------------------------------------------------")
    print("Seeding initial company, settings, and Admin user...")
    from django.core.management import call_command
    call_command('create_first_admin')
    with connection.cursor() as cursor:
        try:
            cursor.execute("SELECT seed_module8_company_defaults(company_id) FROM companies;")
            print("Module 8 defaults seeded (Categories, Request Types, Resolution Outcomes).")
        except Exception as seed_err:
            print(f"[!] Module 8 seed notice: {seed_err}")
        try:
            cursor.execute("SELECT seed_module9_company_defaults(company_id) FROM companies;")
            print("Module 9 defaults seeded (Escalation Configs).")
        except Exception as seed_err:
            print(f"[!] Module 9 seed notice: {seed_err}")
        try:
            cursor.execute("SELECT seed_module10_company_defaults(company_id) FROM companies;")
            print("Module 10 defaults seeded (Client Portal Configs).")
        except Exception as seed_err:
            print(f"[!] Module 10 seed notice: {seed_err}")
        try:
            cursor.execute("SELECT seed_module12_company_defaults(company_id) FROM companies;")
            print("Module 12 defaults seeded (HQ Armoury, Master Licences, Weapons, Ammunition Lots).")
        except Exception as seed_err:
            print(f"[!] Module 12 seed notice: {seed_err}")
        try:
            cursor.execute("SELECT seed_module13_company_defaults(company_id) FROM companies;")
            print("Module 13 defaults seeded (Reports, 81 Metrics & Dictionary Versions).")
        except Exception as seed_err:
            print(f"[!] Module 13 seed notice: {seed_err}")
    print("==================================================")
    print("Database ready! Admin credentials:")
    print("  Email:    admin@securityagency.local")
    print("  Password: AdminPass123!")
    print("Run `python manage.py test` to verify complete test suite.")
    print("==================================================")

if __name__ == '__main__':
    try:
        initialize_database()
    except Exception as e:
        print(f"\n[ERROR] Database initialization failed: {e}")
        sys.exit(1)
