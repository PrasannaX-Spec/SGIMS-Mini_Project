import logging
from django.core.management.base import BaseCommand
from django.contrib.auth.hashers import make_password
from foundation.models import User
from foundation.services.auth_service import validate_password_strength, revoke_all_user_sessions
from foundation.services.audit_service import write_audit_event

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Resets an Admin password and unlocks the account (FR-1.15, AC-59)."

    def add_arguments(self, parser):
        parser.add_argument('--email', type=str, required=True, help='Email of the Admin account')
        parser.add_argument('--password', type=str, required=True, help='New password for the Admin')

    def handle(self, *args, **options):
        email = options['email'].lower()
        new_password = options['password']

        user = User.objects.filter(email__iexact=email, role='ADMIN').first()
        if not user:
            self.stderr.write(self.style.ERROR(f"No Admin user found with email: {email}"))
            return

        try:
            validate_password_strength(new_password, email)
        except ValueError as e:
            self.stderr.write(self.style.ERROR(f"Password validation error: {e}"))
            return

        user.password_hash = make_password(new_password)
        user.status = 'ACTIVE'
        user.failed_attempts = 0
        user.locked_until = None
        user.must_change_password = False
        user.save()

        # Revoke all sessions
        revoke_all_user_sessions(user, reason='PASSWORD_CHANGE')

        # Log to server log and audit log (FR-1.15, AC-59)
        logger.warning(f"Admin account {email} was reset and unlocked via server command reset_admin.")

        write_audit_event(
            action_code='auth.unlock',
            actor_user=None,  # System
            record_type='User',
            record_id=str(user.user_id),
            reason="Admin password reset and account unlocked via server command reset_admin (FR-1.15)",
            old_values={'locked': True},
            new_values={'locked': False},
            result='SUCCESS',
            company_id=user.company_id
        )

        self.stdout.write(self.style.SUCCESS(f"Successfully reset password and unlocked Admin account: {email}"))

