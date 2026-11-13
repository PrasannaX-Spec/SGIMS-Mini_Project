import csv
import io
from datetime import datetime, date, timedelta
from decimal import Decimal
from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import ValidationError, PermissionDenied, NotFound

from master_data.models import (
    Company, Client, ClientContact, ClientSite, SiteGeofence,
    SiteSupervisorAssignment, PostType, ShiftTemplate, SiteShift,
    SiteManpowerRequirement, ServiceAgreement, ClientBillingRate
)
from foundation.models import User, ScopeGrant
from foundation.services.audit_service import write_audit_event
from foundation.services.settings_service import get_setting


INDIA_LAT_BOUNDS = (6.0, 38.0)
INDIA_LON_BOUNDS = (68.0, 98.0)
KARNATAKA_LAT_BOUNDS = (11.5, 18.5)
KARNATAKA_LON_BOUNDS = (74.0, 78.6)


def validate_coordinates(lat, lon):
    try:
        lat = float(lat)
        lon = float(lon)
    except (TypeError, ValueError):
        raise ValidationError({'coordinates': 'Latitude and longitude must be valid numeric values.'})

    if not (INDIA_LAT_BOUNDS[0] <= lat <= INDIA_LAT_BOUNDS[1] and INDIA_LON_BOUNDS[0] <= lon <= INDIA_LON_BOUNDS[1]):
        raise ValidationError({'coordinates': f"Coordinates ({lat}, {lon}) are outside India boundaries."})

    is_karnataka = (KARNATAKA_LAT_BOUNDS[0] <= lat <= KARNATAKA_LAT_BOUNDS[1] and 
                    KARNATAKA_LON_BOUNDS[0] <= lon <= KARNATAKA_LON_BOUNDS[1])
    return lat, lon, is_karnataka


def get_company_profile(company_id):
    try:
        return Company.objects.get(company_id=company_id)
    except Company.DoesNotExist:
        raise NotFound("Company profile not found.")


def update_company_profile(company_id, data, actor_user, request=None):
    company = get_company_profile(company_id)
    allowed_fields = [
        'legal_name', 'trade_name', 'registration_no', 'pan', 'gstin', 'email', 'phone',
        'address_line1', 'address_line2', 'city', 'district', 'state_code',
        'postal_code', 'psara_number', 'psara_validity', 'logo_url'
    ]
    for field in allowed_fields:
        if field in data:
            setattr(company, field, data[field])

    company.save()
    write_audit_event(
        actor_user=actor_user,
        action_code='company.update',
        record_type='COMPANY',
        record_id=company.company_id,
        reason='Updated company profile',
        new_values={'legal_name': company.legal_name},
        request=request
    )
    return company


def create_client(company_id, data, actor_user, request=None):
    client_code = data.get('client_code', '').strip().upper()
    if not client_code:
        raise ValidationError({'client_code': 'Client code is required.'})

    if Client.objects.filter(company_id=company_id, client_code=client_code).exists():
        raise ValidationError({'client_code': f"Client with code '{client_code}' already exists."})

    client = Client.objects.create(
        company_id=company_id,
        client_code=client_code,
        legal_name=data.get('legal_name', '').strip(),
        display_name=data.get('display_name', data.get('legal_name', '')).strip(),
        pan=data.get('pan', '').strip().upper() if data.get('pan') else None,
        gstin=data.get('gstin', '').strip().upper() if data.get('gstin') else None,
        billing_email=data.get('billing_email'),
        billing_phone=data.get('billing_phone'),
        billing_address=data.get('billing_address'),
        notes=data.get('notes'),
        status=data.get('status', 'active')
    )

    write_audit_event(
        actor_user=actor_user,
        action_code='client.create',
        record_type='CLIENT',
        record_id=client.client_id,
        reason=f"Created client {client.client_code} - {client.legal_name}",
        new_values={'client_code': client.client_code, 'status': client.status},
        request=request
    )
    return client


def update_client(client_id, data, actor_user, request=None):
    client = Client.objects.get(client_id=client_id)
    allowed_fields = [
        'legal_name', 'display_name', 'pan', 'gstin', 'billing_email',
        'billing_phone', 'billing_address', 'notes', 'status'
    ]
    for field in allowed_fields:
        if field in data:
            setattr(client, field, data[field])

    client.save()
    write_audit_event(
        actor_user=actor_user,
        action_code='client.update',
        record_type='CLIENT',
        record_id=client.client_id,
        reason=f"Updated client {client.client_code}",
        new_values={'status': client.status},
        request=request
    )
    return client


def add_client_contact(client_id, data, actor_user, request=None):
    client = Client.objects.get(client_id=client_id)
    contact_name = data.get('contact_name', '').strip()
    phone = data.get('phone', '').strip()
    if not contact_name or not phone:
        raise ValidationError({'detail': 'Contact name and phone are required.'})

    is_primary = data.get('is_primary', False)
    if is_primary:
        ClientContact.objects.filter(client=client, is_primary=True).update(is_primary=False)

    contact = ClientContact.objects.create(
        client=client,
        contact_name=contact_name,
        designation=data.get('designation'),
        email=data.get('email'),
        phone=phone,
        contact_role=data.get('contact_role', 'general'),
        contact_type=data.get('contact_role', 'general'),
        is_primary=is_primary,
        is_active=True
    )
    return contact


def create_site(client_id, data, actor_user, request=None):
    client = Client.objects.get(client_id=client_id)
    site_code = data.get('site_code', '').strip().upper()
    if not site_code:
        raise ValidationError({'site_code': 'Site code is required.'})

    if ClientSite.objects.filter(client=client, site_code=site_code).exists():
        raise ValidationError({'site_code': f"Site code '{site_code}' already exists for this client."})

    lat = data.get('latitude')
    lon = data.get('longitude')
    radius = data.get('geofence_radius_m', 100)

    if lat is not None and lon is not None:
        lat, lon, _ = validate_coordinates(lat, lon)

    site = ClientSite.objects.create(
        client=client,
        site_code=site_code,
        site_name=data.get('site_name', '').strip(),
        operational_status=data.get('operational_status', 'planned'),
        address_line1=data.get('address_line1', 'N/A'),
        address_line2=data.get('address_line2'),
        city=data.get('city'),
        district=data.get('district'),
        state_code=data.get('state_code', 'KA'),
        postal_code=data.get('postal_code'),
        latitude=lat,
        longitude=lon,
        geofence_radius_m=int(radius) if radius else None,
        guard_instructions=data.get('guard_instructions')
    )

    if lat and lon and radius:
        SiteGeofence.objects.create(
            site=site,
            version=1,
            latitude=lat,
            longitude=lon,
            radius_meters=radius,
            is_active=True,
            effective_from=timezone.now(),
            reason_for_change='Initial site creation',
            created_by_user_id=actor_user.user_id
        )

    write_audit_event(
        actor_user=actor_user,
        action_code='site.create',
        record_type='CLIENT_SITE',
        record_id=site.site_id,
        reason=f"Created site {site.site_code} - {site.site_name}",
        new_values={'site_code': site.site_code, 'status': site.operational_status},
        request=request
    )
    return site


def update_site_geofence(site_id, lat, lon, radius, reason, actor_user, request=None):
    site = ClientSite.objects.get(site_id=site_id)
    lat, lon, _ = validate_coordinates(lat, lon)

    min_rad = int(get_setting('geofence_min_radius_m', site.client.company_id))
    max_rad = int(get_setting('geofence_max_radius_m', site.client.company_id))

    if not (min_rad <= float(radius) <= max_rad):
        raise ValidationError({'radius_meters': f"Geofence radius must be between {min_rad}m and {max_rad}m."})

    now = timezone.now()

    with transaction.atomic():
        current_active = SiteGeofence.objects.filter(site=site, is_active=True).order_by('-version').first()
        next_version = 1
        if current_active:
            next_version = current_active.version + 1
            current_active.is_active = False
            current_active.effective_to = now
            current_active.save()

        new_geofence = SiteGeofence.objects.create(
            site=site,
            version=next_version,
            latitude=lat,
            longitude=lon,
            radius_meters=radius,
            is_active=True,
            effective_from=now,
            reason_for_change=reason or 'Geofence updated',
            created_by_user_id=actor_user.user_id
        )

        site.latitude = lat
        site.longitude = lon
        site.geofence_radius_m = int(radius)
        site.save()

    write_audit_event(
        actor_user=actor_user,
        action_code='site.geofence_update',
        record_type='SITE_GEOFENCE',
        record_id=new_geofence.geofence_id,
        reason=f"Updated geofence for site {site.site_code} (v{next_version}, radius: {radius}m)",
        new_values={'version': next_version, 'lat': str(lat), 'lon': str(lon), 'radius': str(radius)},
        request=request
    )
    return new_geofence


def assign_site_supervisor(site_id, supervisor_user_id, role_type, reason, actor_user, request=None):
    site = ClientSite.objects.get(site_id=site_id)
    supervisor = User.objects.get(user_id=supervisor_user_id)

    if supervisor.role != 'SUPERVISOR' or supervisor.status != 'ACTIVE':
        raise ValidationError({'supervisor': 'User must be an active SUPERVISOR.'})

    if not reason or not reason.strip():
        raise ValidationError({'assignment_reason': 'Reason for assignment/reassignment is mandatory.'})

    now = timezone.now()

    with transaction.atomic():
        if role_type == 'primary':
            prev_primary = SiteSupervisorAssignment.objects.filter(
                site=site, role_type='primary', is_active=True
            ).first()
            if prev_primary:
                prev_primary.is_active = False
                prev_primary.effective_to = now
                prev_primary.save()

        assignment = SiteSupervisorAssignment.objects.create(
            site=site,
            supervisor_user_id=supervisor.user_id,
            role_type=role_type,
            effective_from=now,
            is_active=True,
            assignment_reason=reason.strip(),
            assigned_by_user_id=actor_user.user_id
        )

        ScopeGrant.objects.get_or_create(
            user=supervisor,
            company_id=site.client.company_id,
            scope_type='SITE',
            target_id=site.site_id,
            defaults={'created_by': actor_user, 'effective_from': timezone.now().date()}
        )

    write_audit_event(
        actor_user=actor_user,
        action_code='site.supervisor_assigned',
        record_type='SUPERVISOR_ASSIGNMENT',
        record_id=assignment.assignment_id,
        reason=f"Assigned {supervisor.full_name} as {role_type} supervisor to site {site.site_code}",
        new_values={'supervisor_id': str(supervisor.user_id), 'role': role_type, 'reason': reason},
        request=request
    )
    return assignment


def calculate_shift_duration(start_time, end_time):
    start_dt = datetime.combine(date.today(), start_time)
    end_dt = datetime.combine(date.today(), end_time)
    is_cross_midnight = False

    if end_dt <= start_dt:
        end_dt += timedelta(days=1)
        is_cross_midnight = True

    duration_minutes = int((end_dt - start_dt).total_seconds() / 60)
    return duration_minutes, is_cross_midnight


def create_site_shift(site_id, data, actor_user, request=None):
    site = ClientSite.objects.get(site_id=site_id)
    shift_code = data.get('shift_code', '').strip().upper()
    shift_name = data.get('shift_name', '').strip()

    if not shift_code or not shift_name:
        raise ValidationError({'detail': 'Shift code and name are required.'})

    start_time_val = data.get('start_time')
    end_time_val = data.get('end_time')

    start_time = datetime.strptime(start_time_val, '%H:%M:%S' if len(start_time_val) == 8 else '%H:%M').time()
    end_time = datetime.strptime(end_time_val, '%H:%M:%S' if len(end_time_val) == 8 else '%H:%M').time()

    duration_minutes, is_cross_midnight = calculate_shift_duration(start_time, end_time)

    max_shift_min = int(get_setting('max_shift_duration_minutes', site.client.company_id))
    if duration_minutes > max_shift_min:
        raise ValidationError({'duration': f"Shift duration ({duration_minutes}m) exceeds maximum limit of {max_shift_min}m."})

    shift = SiteShift.objects.create(
        site=site,
        shift_code=shift_code,
        shift_name=shift_name,
        start_time=start_time,
        end_time=end_time,
        duration_minutes=duration_minutes,
        is_cross_midnight=is_cross_midnight,
        is_active=True
    )
    return shift


def set_manpower_requirement(site_id, shift_id, post_type_id, count, effective_from, actor_user, effective_to=None, request=None):
    site = ClientSite.objects.get(site_id=site_id)
    shift = SiteShift.objects.get(shift_id=shift_id, site=site)
    post_type = PostType.objects.get(post_type_id=post_type_id)

    if count <= 0:
        raise ValidationError({'required_count': 'Required count must be greater than zero.'})

    if isinstance(effective_from, str):
        effective_from = datetime.strptime(effective_from, '%Y-%m-%d').date()
    if effective_to and isinstance(effective_to, str):
        effective_to = datetime.strptime(effective_to, '%Y-%m-%d').date()

    with transaction.atomic():
        prev_req = SiteManpowerRequirement.objects.filter(
            site=site, shift=shift, post_type=post_type, is_active=True
        ).order_by('-version').first()

        next_version = 1
        if prev_req:
            next_version = prev_req.version + 1
            prev_req.is_active = False
            prev_req.effective_to = effective_from - timedelta(days=1)
            prev_req.save()

        req = SiteManpowerRequirement.objects.create(
            site=site,
            shift=shift,
            post_type=post_type,
            required_count=count,
            effective_from=effective_from,
            effective_to=effective_to,
            version=next_version,
            is_active=True,
            created_by_user_id=actor_user.user_id
        )
    return req


def set_billing_rate(client_id, post_type_id, amount, rate_type, effective_from, actor_user, site_id=None, effective_to=None, request=None):
    client = Client.objects.get(client_id=client_id)
    post_type = PostType.objects.get(post_type_id=post_type_id)
    site = ClientSite.objects.get(site_id=site_id) if site_id else None

    amount = Decimal(str(amount))
    if amount < 0:
        raise ValidationError({'rate_amount': 'Rate amount cannot be negative.'})

    if isinstance(effective_from, str):
        effective_from = datetime.strptime(effective_from, '%Y-%m-%d').date()
    if effective_to and isinstance(effective_to, str):
        effective_to = datetime.strptime(effective_to, '%Y-%m-%d').date()

    with transaction.atomic():
        prev_rate = ClientBillingRate.objects.filter(
            client=client, site=site, post_type=post_type, is_active=True
        ).order_by('-version').first()

        next_version = 1
        if prev_rate:
            next_version = prev_rate.version + 1
            prev_rate.is_active = False
            prev_rate.effective_to = effective_from - timedelta(days=1)
            prev_rate.save()

        rate = ClientBillingRate.objects.create(
            client=client,
            site=site,
            post_type=post_type,
            rate_type=rate_type,
            rate_amount=amount,
            effective_from=effective_from,
            effective_to=effective_to,
            version=next_version,
            is_active=True,
            created_by_user_id=actor_user.user_id
        )
    return rate


def resolve_billing_rate(client_id, post_type_id, target_date, site_id=None):
    from django.db.models import Q
    if isinstance(target_date, str):
        target_date = datetime.strptime(target_date, '%Y-%m-%d').date()

    q_date = Q(effective_to__isnull=True) | Q(effective_to__gte=target_date)

    if site_id:
        site_rate = ClientBillingRate.objects.filter(
            client_id=client_id,
            site_id=site_id,
            post_type_id=post_type_id,
            effective_from__lte=target_date,
            is_active=True
        ).filter(q_date).order_by('-effective_from', '-version').first()

        if site_rate:
            return site_rate, 'site_specific'

    client_default = ClientBillingRate.objects.filter(
        client_id=client_id,
        site_id__isnull=True,
        post_type_id=post_type_id,
        effective_from__lte=target_date,
        is_active=True
    ).filter(q_date).order_by('-effective_from', '-version').first()

    if client_default:
        return client_default, 'client_default'

    return None, 'not_found'


def create_service_agreement(client_id, data, actor_user, request=None):
    client = Client.objects.get(client_id=client_id)
    ref = data.get('agreement_reference', '').strip()
    if not ref:
        raise ValidationError({'agreement_reference': 'Agreement reference is required.'})

    start_date = data.get('start_date')
    end_date = data.get('end_date')

    if isinstance(start_date, str):
        start_date = datetime.strptime(start_date, '%Y-%m-%d').date()
    if isinstance(end_date, str):
        end_date = datetime.strptime(end_date, '%Y-%m-%d').date()

    if end_date < start_date:
        raise ValidationError({'end_date': 'End date must be greater than or equal to start date.'})

    site_id = data.get('site_id')
    site = ClientSite.objects.get(site_id=site_id) if site_id else None

    agreement = ServiceAgreement.objects.create(
        client=client,
        site=site,
        agreement_reference=ref,
        start_date=start_date,
        end_date=end_date,
        document_path=data.get('document_path'),
        document_filename=data.get('document_filename'),
        document_mime_type=data.get('document_mime_type'),
        notes=data.get('notes'),
        is_active=True,
        created_by_user_id=actor_user.user_id
    )
    return agreement


def import_clients_csv(csv_content, company_id, actor_user, request=None):
    reader = csv.DictReader(io.StringIO(csv_content))
    rows = list(reader)
    if not rows:
        raise ValidationError({'detail': 'CSV file is empty.'})

    errors = []
    clients_to_create = []
    seen_codes = set()

    for idx, row in enumerate(rows, start=1):
        code = row.get('client_code', '').strip().upper()
        name = row.get('legal_name', '').strip()

        if not code:
            errors.append(f"Row {idx}: client_code is required.")
        elif code in seen_codes:
            errors.append(f"Row {idx}: duplicate client_code '{code}' in CSV.")
        elif Client.objects.filter(company_id=company_id, client_code=code).exists():
            errors.append(f"Row {idx}: client_code '{code}' already exists in database.")
        else:
            seen_codes.add(code)

        if not name:
            errors.append(f"Row {idx}: legal_name is required.")

        clients_to_create.append({
            'company_id': company_id,
            'client_code': code,
            'legal_name': name,
            'pan': row.get('pan', '').strip().upper() if row.get('pan') else None,
            'gstin': row.get('gstin', '').strip().upper() if row.get('gstin') else None,
            'status': 'active'
        })

    if errors:
        raise ValidationError({'import_errors': errors})

    created = []
    with transaction.atomic():
        for item in clients_to_create:
            c = Client.objects.create(**item)
            created.append(c)

    return len(created)
