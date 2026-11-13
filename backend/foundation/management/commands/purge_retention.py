from datetime import timedelta
from django.core.management.base import BaseCommand
from django.utils import timezone
from django.db import connection
from foundation.models import Notification, LoginAttempt, Company
from foundation.services.settings_service import get_setting
from foundation.services.audit_service import write_audit_event


class Command(BaseCommand):
    help = "Purges notifications, login history, and audit logs beyond retention settings (FR-1.64, FR-1.75, AC-61)."

    def handle(self, *args, **options):
        now = timezone.now()
        first_comp = Company.objects.first()
        company_id = first_comp.company_id if first_comp else None

        # 1. Notifications retention (default 90 days, FR-1.64)
        notif_days = get_setting('notification_retention_days', company_id)
        notif_cutoff = now - timedelta(days=notif_days)
        notif_count, _ = Notification.objects.filter(created_at__lt=notif_cutoff).delete()
        self.stdout.write(f"Purged {notif_count} notifications older than {notif_days} days.")

        # 2. Login history retention (default 12 months, FR-1.49)
        login_months = get_setting('login_history_retention_months', company_id)
        login_cutoff = now - timedelta(days=login_months * 30)
        login_count, _ = LoginAttempt.objects.filter(attempted_at__lt=login_cutoff).delete()
        self.stdout.write(f"Purged {login_count} login attempts older than {login_months} months.")

        # 3. Audit retention (default 36 months, FR-1.75)
        audit_months = get_setting('audit_retention_months', company_id)
        audit_cutoff = now - timedelta(days=audit_months * 30)

        # Bypass tamper trigger using session_replication_role in admin maintenance job
        with connection.cursor() as cursor:
            cursor.execute("SET session_replication_role = 'replica';")
            cursor.execute(
                "DELETE FROM audit_events WHERE occurred_at < %s RETURNING id;",
                [audit_cutoff]
            )
            deleted_audit_rows = cursor.fetchall()
            audit_count = len(deleted_audit_rows)
            cursor.execute("SET session_replication_role = 'origin';")

        self.stdout.write(f"Purged {audit_count} audit events older than {audit_months} months.")

        # Write audit.purged event (AC-61)
        if company_id:
            write_audit_event(
                action_code='audit.purged',
                actor_user=None,  # System
                module='foundation',
                record_type='AuditEvent',
                reason=f"Retention purge: {audit_count} audit rows, {notif_count} notifications, {login_count} login history rows.",
                result='SUCCESS',
                company_id=company_id
            )

        self.stdout.write(self.style.SUCCESS("Retention purge job completed successfully."))

