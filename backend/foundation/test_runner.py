from pathlib import Path
from django.test.runner import DiscoverRunner
from django.db import connection


class PostgreSQLSchemaTestRunner(DiscoverRunner):
    """
    Test runner that executes our ERP database schemas on the test database
    so unmanaged models have their tables, schemas, and triggers in tests.
    """
    def setup_databases(self, **kwargs):
        config = super().setup_databases(**kwargs)

        base_dir = Path(__file__).resolve().parent.parent.parent
        schema1_path = base_dir / "security_agency_erp_schema_postgresql.sql"
        schema2_path = base_dir / "module1_foundation_schema.sql"
        schema3_path = base_dir / "module2_master_data_schema.sql"
        schema4_path = base_dir / "module3_guard_management_schema.sql"
        schema5_path = base_dir / "module4_service_quotation_schema.sql"
        schema6_path = base_dir / "module5_deployment_roster_schema.sql"
        schema7_path = base_dir / "module6_attendance_schema.sql"
        schema8_path = base_dir / "module7_live_monitoring_schema.sql"
        schema9_path = base_dir / "module8_incident_request_schema.sql"
        schema10_path = base_dir / "module9_panic_escalation_schema.sql"
        schema11_path = base_dir / "module10_client_portal_schema.sql"
        schema12_path = base_dir / "module11_billing_invoices_schema.sql"

        with connection.cursor() as cursor:
            cursor.execute("DROP SCHEMA IF EXISTS security_erp CASCADE;")
            if schema1_path.exists():
                with open(schema1_path, "r", encoding="utf-8") as f:
                    cursor.execute(f.read())
            if schema2_path.exists():
                with open(schema2_path, "r", encoding="utf-8") as f:
                    cursor.execute(f.read())
            if schema3_path.exists():
                with open(schema3_path, "r", encoding="utf-8") as f:
                    cursor.execute(f.read())
            if schema4_path.exists():
                with open(schema4_path, "r", encoding="utf-8") as f:
                    cursor.execute(f.read())
            if schema5_path.exists():
                with open(schema5_path, "r", encoding="utf-8") as f:
                    cursor.execute(f.read())
            if schema6_path.exists():
                with open(schema6_path, "r", encoding="utf-8") as f:
                    cursor.execute(f.read())
            if schema7_path.exists():
                with open(schema7_path, "r", encoding="utf-8") as f:
                    cursor.execute(f.read())
            if schema8_path.exists():
                with open(schema8_path, "r", encoding="utf-8") as f:
                    cursor.execute(f.read())
            if schema9_path.exists():
                with open(schema9_path, "r", encoding="utf-8") as f:
                    cursor.execute(f.read())
            if schema10_path.exists():
                with open(schema10_path, "r", encoding="utf-8") as f:
                    cursor.execute(f.read())
            if schema11_path.exists():
                with open(schema11_path, "r", encoding="utf-8") as f:
                    cursor.execute(f.read())
            if schema12_path.exists():
                with open(schema12_path, "r", encoding="utf-8") as f:
                    cursor.execute(f.read())

        return config

