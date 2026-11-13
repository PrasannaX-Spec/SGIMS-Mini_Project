import json
from datetime import date, timedelta
from decimal import Decimal
from django.test import TestCase, Client
from django.utils import timezone
from master_data.models import (
    Company, Client as MasterClient, ClientSite, SiteGeofence,
    SiteSupervisorAssignment, PostType, SiteShift,
    SiteManpowerRequirement, ClientBillingRate
)
from master_data import services
from foundation.models import User


class MasterDataTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(
            legal_name='Test Security Services Pvt Ltd',
            trade_name='Test Security Services',
            pan='ABCDE1234F',
            gstin='29ABCDE1234F1Z5',
            state_code='KA',
            is_active=True
        )

        self.admin = User.objects.create(
            company_id=self.company.company_id,
            email='admin@test.local',
            full_name='Master Admin',
            role='ADMIN',
            status='ACTIVE'
        )

        self.supervisor = User.objects.create(
            company_id=self.company.company_id,
            email='supervisor@test.local',
            full_name='Site Supervisor',
            role='SUPERVISOR',
            status='ACTIVE'
        )

        self.guard_user = User.objects.create(
            company_id=self.company.company_id,
            email='guard@test.local',
            full_name='Security Guard',
            role='GUARD',
            status='ACTIVE'
        )

    def test_client_crud_and_code_uniqueness(self):
        client = services.create_client(
            self.company.company_id,
            {'client_code': 'CLI-001', 'legal_name': 'Infosys Campus', 'pan': 'AABCI1234D'},
            self.admin
        )
        self.assertEqual(client.client_code, 'CLI-001')
        self.assertEqual(client.status, 'active')

        # Duplicate code should fail
        with self.assertRaises(Exception):
            services.create_client(
                self.company.company_id,
                {'client_code': 'CLI-001', 'legal_name': 'Duplicate Code Client'},
                self.admin
            )

    def test_site_creation_and_coordinate_validation(self):
        client = services.create_client(
            self.company.company_id,
            {'client_code': 'CLI-002', 'legal_name': 'Wipro Tech Park'},
            self.admin
        )

        # Valid Bangalore coordinates
        site = services.create_site(
            client.client_id,
            {
                'site_code': 'SITE-BLR-01',
                'site_name': 'Wipro Electronic City Gate 1',
                'latitude': 12.8452,
                'longitude': 77.6602,
                'geofence_radius_m': 100
            },
            self.admin
        )
        self.assertEqual(site.site_code, 'SITE-BLR-01')
        self.assertEqual(site.geofences.count(), 1)
        self.assertEqual(site.geofences.first().version, 1)

        # Coordinates outside India must fail
        with self.assertRaises(Exception):
            services.create_site(
                client.client_id,
                {
                    'site_code': 'SITE-NY-01',
                    'site_name': 'New York Office',
                    'latitude': 40.7128,
                    'longitude': -74.0060,
                },
                self.admin
            )

    def test_geofence_versioning_and_limits(self):
        client = services.create_client(
            self.company.company_id,
            {'client_code': 'CLI-003', 'legal_name': 'Bosch India'},
            self.admin
        )
        site = services.create_site(
            client.client_id,
            {'site_code': 'SITE-BOSCH-01', 'site_name': 'Bosch Adugodi', 'latitude': 12.935, 'longitude': 77.605, 'geofence_radius_m': 50},
            self.admin
        )

        # Update geofence creates version 2
        gf2 = services.update_site_geofence(
            site.site_id, 12.936, 77.606, 120, 'Expanded perimeter gate', self.admin
        )
        self.assertEqual(gf2.version, 2)
        self.assertTrue(gf2.is_active)

        # Prior version 1 should now be inactive
        gf1 = SiteGeofence.objects.get(site=site, version=1)
        self.assertFalse(gf1.is_active)
        self.assertIsNotNone(gf1.effective_to)

    def test_supervisor_assignment_and_mandatory_reason(self):
        client = services.create_client(
            self.company.company_id,
            {'client_code': 'CLI-004', 'legal_name': 'TCS Park'},
            self.admin
        )
        site = services.create_site(
            client.client_id,
            {'site_code': 'SITE-TCS-01', 'site_name': 'TCS Whitefield'},
            self.admin
        )

        # Missing reason must fail
        with self.assertRaises(Exception):
            services.assign_site_supervisor(
                site.site_id, self.supervisor.user_id, 'primary', '', self.admin
            )

        # Non-supervisor role must fail
        with self.assertRaises(Exception):
            services.assign_site_supervisor(
                site.site_id, self.guard_user.user_id, 'primary', 'Assigned guard as supervisor', self.admin
            )

        # Valid primary supervisor assignment
        assign = services.assign_site_supervisor(
            site.site_id, self.supervisor.user_id, 'primary', 'Initial site deployment', self.admin
        )
        self.assertTrue(assign.is_active)
        self.assertEqual(assign.role_type, 'primary')

    def test_cross_midnight_shift_duration(self):
        client = services.create_client(
            self.company.company_id,
            {'client_code': 'CLI-005', 'legal_name': 'Dell Technologies'},
            self.admin
        )
        site = services.create_site(
            client.client_id,
            {'site_code': 'SITE-DELL-01', 'site_name': 'Dell Domlur'},
            self.admin
        )

        # Night shift: 22:00 to 06:00 (8 hours = 480 mins)
        shift = services.create_site_shift(
            site.site_id,
            {
                'shift_code': 'NIGHT',
                'shift_name': 'Night Shift',
                'start_time': '22:00',
                'end_time': '06:00'
            },
            self.admin
        )
        self.assertTrue(shift.is_cross_midnight)
        self.assertEqual(shift.duration_minutes, 480)

    def test_billing_rate_resolution_precedence(self):
        client = services.create_client(
            self.company.company_id,
            {'client_code': 'CLI-006', 'legal_name': 'Biocon Park'},
            self.admin
        )
        site = services.create_site(
            client.client_id,
            {'site_code': 'SITE-BIO-01', 'site_name': 'Biocon R&D'},
            self.admin
        )
        post_type = PostType.objects.create(
            company=self.company,
            code='SG',
            name='Security Guard'
        )

        today = date.today()

        # 1. Set client default rate: ₹120/hr
        services.set_billing_rate(
            client.client_id, post_type.post_type_id, 120.00, 'hourly', today, self.admin
        )

        # Resolving for site without site-specific rate returns client default
        rate, source = services.resolve_billing_rate(
            client.client_id, post_type.post_type_id, today, site_id=site.site_id
        )
        self.assertEqual(source, 'client_default')
        self.assertEqual(Decimal(str(rate.rate_amount)), Decimal('120.00'))

        # 2. Set site-specific rate: ₹150/hr
        services.set_billing_rate(
            client.client_id, post_type.post_type_id, 150.00, 'hourly', today, self.admin, site_id=site.site_id
        )

        # Resolving now returns site-specific rate (precedence check)
        rate, source = services.resolve_billing_rate(
            client.client_id, post_type.post_type_id, today, site_id=site.site_id
        )
        self.assertEqual(source, 'site_specific')
        self.assertEqual(Decimal(str(rate.rate_amount)), Decimal('150.00'))
