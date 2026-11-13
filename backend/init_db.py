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

from django.db import connection

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
    ]

    print("==================================================")
    print("Security Agency ERP - Database Initializer")
    print("==================================================")
    print(f"Target Database: {connection.settings_dict.get('NAME')}")
    print(f"Target Host:     {connection.settings_dict.get('HOST')}:{connection.settings_dict.get('PORT')}")
    print(f"Target User:     {connection.settings_dict.get('USER')}")
    print("--------------------------------------------------")

    with connection.cursor() as cursor:
        for name, file_path in schemas:
            if not file_path.exists():
                print(f"[!] Warning: File not found: {file_path.name}")
                continue

            print(f"Applying: {name} ({file_path.name})...", end="", flush=True)
            with open(file_path, "r", encoding="utf-8") as f:
                sql_content = f.read()
                cursor.execute(sql_content)
            print(" [OK]")

    print("==================================================")
    print("All ERP database schemas applied successfully!")
    print("--------------------------------------------------")
    print("Seeding initial company, settings, and Admin user...")
    from django.core.management import call_command
    call_command('create_first_admin')
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
