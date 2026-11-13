from django.core.management.base import BaseCommand
from django.contrib.auth.hashers import make_password
from foundation.models import Company, User, ScopeGrant
from foundation.services.settings_service import initialize_default_settings
from foundation.services.notification_service import sync_notification_types_to_db
from foundation.services.audit_service import write_audit_event


class Command(BaseCommand):
    help = "Initializes the first Company, default settings, and Admin user (PRD Section 2, T3)."

    def add_arguments(self, parser):
        parser.add_argument('--email', type=str, default='admin@securityagency.local', help='Admin email address')
        parser.add_argument('--password', type=str, default='AdminPass123!', help='Admin password')
        parser.add_argument('--name', type=str, default='System Administrator', help='Admin full name')
        parser.add_argument('--company', type=str, default='Karnataka Security Services Ltd', help='Company name')

    def handle(self, *args, **options):
        email = options['email'].lower()
        password = options['password']
        name = options['name']
        company_name = options['company']

        company, comp_created = Company.objects.get_or_create(
            legal_name=company_name,
            defaults={
                'trade_name': company_name,
                'country_code': 'IN',
                'state_code': 'KA',
                'time_zone': 'Asia/Kolkata',
                'is_active': True
            }
        )
        if comp_created:
            self.stdout.write(self.style.SUCCESS(f"Created company: {company.legal_name}"))

        # Initialize default settings
        initialize_default_settings(company)
        sync_notification_types_to_db()

        user, user_created = User.objects.get_or_create(
            email=email,
            company=company,
            defaults={
                'full_name': name,
                'role': 'ADMIN',
                'password_hash': make_password(password),
                'status': 'ACTIVE',
                'must_change_password': False
            }
        )

        if not user_created:
            user.role = 'ADMIN'
            user.status = 'ACTIVE'
            user.password_hash = make_password(password)
            user.must_change_password = False
            user.failed_attempts = 0
            user.locked_until = None
            user.save()
            self.stdout.write(self.style.SUCCESS(f"Updated existing admin account: {email}"))
        else:
            self.stdout.write(self.style.SUCCESS(f"Created new admin account: {email}"))

        # Ensure ALL scope grant exists for Admin (FR-1.32, Section 9)
        ScopeGrant.objects.get_or_create(
            company=company,
            user=user,
            scope_type='ALL',
            effective_from='2020-01-01'
        )

        write_audit_event(
            action_code='user.created' if user_created else 'user.edited',
            actor_user=user,
            module='foundation',
            record_type='User',
            record_id=str(user.user_id),
            reason="Created/updated via management command create_first_admin",
            result='SUCCESS',
            company_id=company.company_id
        )

        self.stdout.write(self.style.SUCCESS(
            f"Successfully set up First Admin:\n"
            f"  Email: {email}\n"
            f"  Password: {password}\n"
            f"  Role: ADMIN\n"
            f"  Company: {company.legal_name}"
        ))

