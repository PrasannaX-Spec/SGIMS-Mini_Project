import secrets
from datetime import datetime, date, timedelta
from decimal import Decimal
from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import ValidationError, PermissionDenied, NotFound

from service_quotation.models import (
    ServiceRequest, ServiceRequestLine, ServiceRequestAttachment,
    ServiceRequestComment, ServiceSiteSurvey, Quotation, QuotationVersion,
    QuotationLine, QuotationAcceptance, QuotationCounter, QuotationConversion
)
from master_data.models import (
    Company, Client, ClientSite, PostType, SiteShift,
    SiteManpowerRequirement, ClientBillingRate, ServiceAgreement
)
from foundation.models import User
from foundation.services.audit_service import write_audit_event
from foundation.services.settings_service import get_setting


def generate_request_reference(company_id):
    prefix = get_setting('service_request_code_prefix', company_id) or 'SR'
    count = ServiceRequest.objects.filter(company_id=company_id).count() + 1
    today_str = date.today().strftime('%Y%m')
    ref = f"{prefix}-{today_str}-{count:04d}"
    while ServiceRequest.objects.filter(request_reference=ref).exists():
        count += 1
        ref = f"{prefix}-{today_str}-{count:04d}"
    return ref


def generate_quotation_reference(company_id):
    prefix = get_setting('quotation_code_prefix', company_id) or 'QT'
    count = Quotation.objects.filter(company_id=company_id).count() + 1
    today_str = date.today().strftime('%Y%m')
    ref = f"{prefix}-{today_str}-{count:04d}"
    while Quotation.objects.filter(quotation_no=ref).exists():
        count += 1
        ref = f"{prefix}-{today_str}-{count:04d}"
    return ref


# ==============================================================================
# 1. SERVICE REQUEST SERVICE (FR-4.9 to FR-4.42, AC-05 to AC-16)
# ==============================================================================

def create_service_request(client_id, data, actor_user, request=None):
    client = Client.objects.get(client_id=client_id)
    submission_ref = data.get('submission_reference')

    # Idempotent duplicate protection (FR-4.42, AC-11, AC-12, E-01)
    if submission_ref:
        existing = ServiceRequest.objects.filter(submission_reference=submission_ref).first()
        if existing:
            return existing

    start_date_val = data.get('start_date')
    if not start_date_val:
        raise ValidationError({'start_date': 'Start date is required.'})

    start_date = datetime.strptime(start_date_val, '%Y-%m-%d').date() if isinstance(start_date_val, str) else start_date_val
    duration_type = data.get('duration_type', 'ongoing')
    end_date_val = data.get('end_date')
    end_date = None

    if end_date_val:
        end_date = datetime.strptime(end_date_val, '%Y-%m-%d').date() if isinstance(end_date_val, str) else end_date_val
        if end_date < start_date:
            raise ValidationError({'end_date': 'End date must be greater than or equal to start date (AC-10, E-07).'})

    # Manpower line requirements (AC-09, FR-4.18)
    lines_data = data.get('manpower_lines') or data.get('lines') or []
    if not lines_data and data.get('status') == 'submitted':
        raise ValidationError({'manpower_lines': 'At least one manpower requirement line is required before submission (AC-09).'})

    ref = generate_request_reference(client.company_id)
    req_status = data.get('status', 'submitted')

    with transaction.atomic():
        sr = ServiceRequest.objects.create(
            company_id=client.company_id,
            client=client,
            request_reference=ref,
            submission_reference=submission_ref,
            existing_site_id=data.get('existing_site_id'),
            new_site_name=data.get('new_site_name'),
            new_site_address=data.get('new_site_address'),
            new_site_latitude=data.get('new_site_latitude'),
            new_site_longitude=data.get('new_site_longitude'),
            service_purpose=data.get('service_purpose', 'office'),
            start_date=start_date,
            duration_type=duration_type,
            end_date=end_date,
            site_contact_name=data.get('site_contact_name', 'Operations Contact'),
            site_contact_phone=data.get('site_contact_phone', client.billing_phone or '+910000000000'),
            special_requirements=data.get('special_requirements'),
            status=req_status,
            created_by_user_id=actor_user.user_id
        )

        for l in lines_data:
            pt = PostType.objects.get(post_type_id=l['post_type_id'])
            # Auto-default armed required from post type (AC-08, FR-4.21)
            armed = l.get('armed_required', pt.requires_armed_authorization)
            ServiceRequestLine.objects.create(
                request=sr,
                post_type=pt,
                guard_count=int(l.get('guard_count', 1)),
                shift_information=l.get('shift_information', 'Standard Day Shift (8h)'),
                hours_per_day=Decimal(str(l.get('hours_per_day', 8.0))),
                working_days=l.get('working_days', ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat']),
                armed_required=armed
            )

    write_audit_event(
        action_code='service_request.create',
        actor_user=actor_user,
        module='service_quotation',
        record_type='SERVICE_REQUEST',
        record_id=str(sr.request_id),
        new_values={'reference': sr.request_reference, 'status': sr.status},
        reason=f"Created service request {sr.request_reference} for client {client.client_code}",
        request=request
    )
    return sr


def request_service_clarification(request_id, question, actor_user, request=None):
    sr = ServiceRequest.objects.get(request_id=request_id)
    if not question or not question.strip():
        raise ValidationError({'question': 'Clarification message cannot be empty.'})

    sr.status = 'awaiting_client'
    sr.save()

    comment = ServiceRequestComment.objects.create(
        request=sr,
        sender_user_id=actor_user.user_id,
        sender_role=actor_user.role,
        message=question.strip(),
        is_clarification_request=True
    )

    write_audit_event(
        action_code='service_request.clarification_requested',
        actor_user=actor_user,
        module='service_quotation',
        record_type='SERVICE_REQUEST',
        record_id=str(sr.request_id),
        new_values={'status': 'awaiting_client'},
        reason=f"Requested clarification on {sr.request_reference}: {question}",
        request=request
    )
    return comment


def withdraw_service_request(request_id, actor_user, request=None):
    sr = ServiceRequest.objects.get(request_id=request_id)
    if sr.status in ('converted', 'accepted'):
        raise ValidationError({'detail': 'Accepted or converted service requests cannot be withdrawn (AC-16, E-29).'})

    sr.status = 'withdrawn'
    sr.save()

    write_audit_event(
        action_code='service_request.withdrawn',
        actor_user=actor_user,
        module='service_quotation',
        record_type='SERVICE_REQUEST',
        record_id=str(sr.request_id),
        new_values={'status': 'withdrawn'},
        reason=f"Withdrew service request {sr.request_reference}",
        request=request
    )
    return sr


# ==============================================================================
# 2. MANUAL QUOTATION ENGINE & IMMUTABILITY (FR-4.60 to FR-4.88, AC-17 to AC-22)
# ==============================================================================

def create_quotation(request_id, data, actor_user, request=None):
    sr = ServiceRequest.objects.get(request_id=request_id)
    company_id = sr.company_id
    client = sr.client

    lines_data = data.get('lines', [])
    if not lines_data:
        raise ValidationError({'lines': 'At least one quotation line is required.'})

    validity_days = int(get_setting('quotation_validity_days', company_id) or 15)
    valid_until = data.get('validity_date')
    if valid_until:
        valid_until = datetime.strptime(valid_until, '%Y-%m-%d').date() if isinstance(valid_until, str) else valid_until
    else:
        valid_until = date.today() + timedelta(days=validity_days)

    quote_no = generate_quotation_reference(company_id)

    with transaction.atomic():
        quotation = Quotation.objects.create(
            company_id=company_id,
            client=client,
            request=sr,
            quotation_no=quote_no,
            version_no=1,
            current_version=1,
            issue_date=date.today(),
            valid_until=valid_until,
            status='draft',
            created_by=actor_user.user_id
        )

        subtotal = Decimal('0.00')
        version = QuotationVersion.objects.create(
            quotation=quotation,
            version_number=1,
            quotation_date=date.today(),
            validity_date=valid_until,
            subtotal=Decimal('0.00'),
            tax_note=data.get('tax_note', 'Applicable taxes extra'),
            payment_terms=data.get('payment_terms', 'Net 30 days'),
            additional_terms=data.get('additional_terms'),
            internal_notes=data.get('internal_notes'),  # Strictly Admin-only (FR-4.74, AC-22)
            status='draft',
            created_by_user_id=actor_user.user_id
        )

        for line in lines_data:
            pt = PostType.objects.get(post_type_id=line['post_type_id'])
            count = int(line['headcount'])
            rate = Decimal(str(line['unit_rate']))
            # Line total: manual decimal representation
            line_tot = Decimal(str(line.get('line_total', count * rate)))
            subtotal += line_tot

            QuotationLine.objects.create(
                quotation=quotation,
                quotation_version=version,
                post_type=pt,
                shift_hours=Decimal(str(line.get('shift_hours', 8.0))),
                headcount=count,
                billing_unit=line.get('billing_unit', 'per_guard_per_month'),
                unit_rate=rate,
                line_total=line_tot
            )

        version.subtotal = subtotal
        version.save()

        quotation.subtotal = subtotal
        quotation.total_amount = subtotal
        quotation.save()

        sr.status = 'quoted'
        sr.save()

    write_audit_event(
        action_code='quotation.create',
        actor_user=actor_user,
        module='service_quotation',
        record_type='QUOTATION',
        record_id=str(quotation.quotation_id),
        new_values={'quotation_no': quote_no, 'version': 1, 'subtotal': str(subtotal)},
        reason=f"Prepared manual quotation {quote_no} (v1) for {client.client_code}",
        request=request
    )
    return quotation, version


def send_quotation(quotation_version_id, actor_user, request=None):
    version = QuotationVersion.objects.get(quotation_version_id=quotation_version_id)
    if version.status == 'sent':
        return version

    quotation = version.quotation
    with transaction.atomic():
        version.status = 'sent'
        version.sent_at = timezone.now()
        version.save()

        quotation.status = 'sent'
        quotation.save()

        sr = quotation.request
        if sr:
            sr.status = 'quoted'
            sr.save()

    write_audit_event(
        action_code='quotation.sent',
        actor_user=actor_user,
        module='service_quotation',
        record_type='QUOTATION_VERSION',
        record_id=str(version.quotation_version_id),
        new_values={'version_number': version.version_number, 'status': 'sent'},
        reason=f"Sent quotation {quotation.quotation_no} (v{version.version_number}) to client",
        request=request
    )
    return version


def revise_quotation(quotation_id, data, actor_user, request=None):
    quotation = Quotation.objects.get(quotation_id=quotation_id)
    last_version = QuotationVersion.objects.filter(quotation=quotation).order_by('-version_number').first()
    next_ver_num = (last_version.version_number + 1) if last_version else 1

    lines_data = data.get('lines', [])
    valid_until = data.get('validity_date') or last_version.validity_date

    with transaction.atomic():
        if last_version and last_version.status == 'sent':
            last_version.status = 'superseded'
            last_version.save()

        subtotal = Decimal('0.00')
        new_ver = QuotationVersion.objects.create(
            quotation=quotation,
            version_number=next_ver_num,
            quotation_date=date.today(),
            validity_date=valid_until,
            subtotal=Decimal('0.00'),
            tax_note=data.get('tax_note', last_version.tax_note if last_version else 'Applicable taxes extra'),
            payment_terms=data.get('payment_terms', last_version.payment_terms if last_version else ''),
            additional_terms=data.get('additional_terms', last_version.additional_terms if last_version else ''),
            internal_notes=data.get('internal_notes', last_version.internal_notes if last_version else ''),
            status='draft',
            created_by_user_id=actor_user.user_id
        )

        for line in lines_data:
            pt = PostType.objects.get(post_type_id=line['post_type_id'])
            count = int(line['headcount'])
            rate = Decimal(str(line['unit_rate']))
            line_tot = Decimal(str(line.get('line_total', count * rate)))
            subtotal += line_tot

            QuotationLine.objects.create(
                quotation=quotation,
                quotation_version=new_ver,
                post_type=pt,
                shift_hours=Decimal(str(line.get('shift_hours', 8.0))),
                headcount=count,
                billing_unit=line.get('billing_unit', 'per_guard_per_month'),
                unit_rate=rate,
                line_total=line_tot
            )

        new_ver.subtotal = subtotal
        new_ver.save()

        quotation.current_version = next_ver_num
        quotation.version_no = next_ver_num
        quotation.subtotal = subtotal
        quotation.total_amount = subtotal
        quotation.status = 'revised'
        quotation.save()

        if quotation.request:
            quotation.request.status = 'revised'
            quotation.request.save()

    write_audit_event(
        action_code='quotation.revised',
        actor_user=actor_user,
        module='service_quotation',
        record_type='QUOTATION_VERSION',
        record_id=str(new_ver.quotation_version_id),
        new_values={'version_number': next_ver_num, 'subtotal': str(subtotal)},
        reason=f"Revised quotation {quotation.quotation_no} to v{next_ver_num}",
        request=request
    )
    return new_ver


# ==============================================================================
# 3. CLIENT DECISIONS & NEGOTIATIONS (FR-4.97 to FR-4.117, AC-23 to AC-30)
# ==============================================================================

def accept_quotation(quotation_version_id, confirmation_checked, actor_user, request=None):
    if not confirmation_checked:
        raise ValidationError({'confirmation': 'You must explicitly check the confirmation box to accept the quotation (AC-23).'})

    version = QuotationVersion.objects.get(quotation_version_id=quotation_version_id)
    if version.status != 'sent':
        raise ValidationError({'detail': f"Cannot accept quotation in '{version.status}' status (must be 'sent')."})

    if version.validity_date < date.today():
        version.status = 'expired'
        version.save()
        raise ValidationError({'detail': 'Quotation has expired and cannot be accepted (AC-27, E-13).'})

    quotation = version.quotation

    with transaction.atomic():
        version.status = 'accepted'
        version.save()

        quotation.status = 'accepted'
        quotation.save()

        sr = quotation.request
        if sr:
            sr.status = 'accepted'
            sr.save()

        # Capture complete click-to-accept audit metadata (AC-24, FR-4.101)
        ip = getattr(request, 'client_ip', None) or (request.META.get('REMOTE_ADDR') if request else '127.0.0.1')
        ua = getattr(request, 'user_agent_str', None) or (request.META.get('HTTP_USER_AGENT') if request else 'Web Client')

        QuotationAcceptance.objects.create(
            quotation_version=version,
            client_user_id=actor_user.user_id,
            ip_address=ip,
            device_information=ua,
            agreed_text=f"Confirmed acceptance of quotation {quotation.quotation_no} (v{version.version_number}) for ₹{version.subtotal}.",
            confirmation_value=True
        )

    write_audit_event(
        action_code='quotation.accepted',
        actor_user=actor_user,
        module='service_quotation',
        record_type='QUOTATION_ACCEPTANCE',
        record_id=str(version.quotation_version_id),
        new_values={'version_number': version.version_number, 'amount': str(version.subtotal)},
        reason=f"Client {actor_user.full_name} accepted quotation {quotation.quotation_no} (v{version.version_number})",
        request=request
    )
    return version


def reject_quotation(quotation_version_id, reason_category, comments, actor_user, request=None):
    version = QuotationVersion.objects.get(quotation_version_id=quotation_version_id)
    quotation = version.quotation

    with transaction.atomic():
        version.status = 'rejected'
        version.save()

        quotation.status = 'rejected'
        quotation.save()

        if quotation.request:
            quotation.request.status = 'rejected_by_client'
            quotation.request.save()

    write_audit_event(
        action_code='quotation.rejected',
        actor_user=actor_user,
        module='service_quotation',
        record_type='QUOTATION_VERSION',
        record_id=str(version.quotation_version_id),
        new_values={'reason': reason_category, 'comments': comments},
        reason=f"Client rejected quotation {quotation.quotation_no} (v{version.version_number})",
        request=request
    )
    return version


def counter_quotation(quotation_version_id, comment, proposed_data, actor_user, request=None):
    if not comment or not comment.strip():
        raise ValidationError({'comment': 'Comment is mandatory when countering a quotation (AC-26, FR-4.109).'})

    version = QuotationVersion.objects.get(quotation_version_id=quotation_version_id)
    if version.status != 'sent':
        raise ValidationError({'detail': 'Can only counter sent quotations (AC-28).'})

    quotation = version.quotation
    company_id = quotation.company_id

    # Negotiation round limits (FR-4.115, AC-30)
    max_rounds = int(get_setting('max_negotiation_rounds', company_id) or 3)
    curr_rounds = QuotationCounter.objects.filter(quotation_version__quotation=quotation).count() + 1
    if curr_rounds > max_rounds:
        raise ValidationError({'detail': f"Maximum negotiation round limit of {max_rounds} reached (AC-30, FR-4.116)."})

    with transaction.atomic():
        counter = QuotationCounter.objects.create(
            quotation_version=version,
            client_user_id=actor_user.user_id,
            comment=comment.strip(),
            proposed_guard_count=proposed_data.get('proposed_guard_count'),
            proposed_rate=proposed_data.get('proposed_rate'),
            proposed_start_date=proposed_data.get('proposed_start_date'),
            negotiation_round=curr_rounds
        )

        # version.status remains 'sent' as it is immutable once sent
        quotation.status = 'countered'
        quotation.save()

        if quotation.request:
            quotation.request.status = 'countered'
            quotation.request.save()

    write_audit_event(
        action_code='quotation.countered',
        actor_user=actor_user,
        module='service_quotation',
        record_type='QUOTATION_COUNTER',
        record_id=str(counter.counter_id),
        new_values={'round': curr_rounds, 'comment': comment},
        reason=f"Client countered quotation {quotation.quotation_no} (Round {curr_rounds})",
        request=request
    )
    return counter


# ==============================================================================
# 4. MODULE 2 DRAFT CONVERSION (FR-4.127 to FR-4.137, AC-31 to AC-36)
# ==============================================================================

def create_draft_setup_from_accepted_quote(quotation_version_id, actor_user, request=None):
    """
    Converts accepted quotation into Module 2 draft master records (AC-31 to AC-36).
    Operation is idempotent and retry-safe: existing created records are reconciled.
    """
    version = QuotationVersion.objects.get(quotation_version_id=quotation_version_id)
    if version.status != 'accepted':
        raise ValidationError({'detail': f"Only accepted quotations can be converted to master data (AC-31). Current status: {version.status}"})

    quotation = version.quotation
    sr = quotation.request
    client = quotation.client
    company_id = quotation.company_id

    # Check for existing conversion
    conv = QuotationConversion.objects.filter(quotation_version=version).first()
    conv_ref = f"CONV-{quotation.quotation_no}-V{version.version_number}"

    if conv and conv.conversion_status == 'completed':
        return conv

    if not conv:
        conv = QuotationConversion.objects.create(
            quotation_version=version,
            conversion_reference=conv_ref,
            conversion_status='pending'
        )

    generated = conv.generated_records or {}

    with transaction.atomic():
        # 1. Site resolution (create draft site if new site requested)
        site = None
        if sr and sr.existing_site_id:
            site = ClientSite.objects.get(site_id=sr.existing_site_id)
        elif 'site_id' in generated:
            site = ClientSite.objects.get(site_id=generated['site_id'])
        else:
            site_code = f"SITE-{client.client_code}-{secrets.token_hex(2).upper()}"
            site = ClientSite.objects.create(
                client=client,
                site_code=site_code,
                site_name=sr.new_site_name or f"New Site for {client.legal_name}",
                address_line1=sr.new_site_address or 'Pending Address',
                operational_status='planned',  # Remains draft/planned (AC-33)
                latitude=sr.new_site_latitude,
                longitude=sr.new_site_longitude,
                geofence_radius_m=100
            )
            generated['site_id'] = str(site.site_id)

        conv.module2_site_id = site.site_id

        # 2. Service Agreement
        agreement = None
        if 'agreement_id' in generated:
            agreement = ServiceAgreement.objects.get(agreement_id=generated['agreement_id'])
        else:
            agreement = ServiceAgreement.objects.create(
                client=client,
                site=site,
                agreement_reference=f"AGR-{quotation.quotation_no}",
                start_date=sr.start_date if sr else date.today(),
                end_date=sr.end_date if (sr and sr.end_date) else (date.today() + timedelta(days=365)),
                is_active=True,
                notes=f"Converted from accepted quotation {quotation.quotation_no} (v{version.version_number})",
                created_by_user_id=actor_user.user_id
            )
            generated['agreement_id'] = str(agreement.agreement_id)

        conv.module2_agreement_id = agreement.agreement_id

        # 3. Manpower requirements & Billing rates from quotation lines
        quote_lines = QuotationLine.objects.filter(quotation_version=version)
        rate_ids = generated.get('rate_ids', [])
        mpr_ids = generated.get('mpr_ids', [])

        for line in quote_lines:
            pt = line.post_type or PostType.objects.filter(company_id=company_id).first()
            if not pt:
                continue

            # Billing rate
            rate = ClientBillingRate.objects.create(
                client=client,
                site=site,
                post_type=pt,
                rate_type='monthly' if line.billing_unit == 'per_guard_per_month' else 'daily',
                rate_amount=line.unit_rate,
                effective_from=sr.start_date if sr else date.today(),
                is_active=True,
                created_by_user_id=actor_user.user_id
            )
            rate_ids.append(str(rate.rate_id))

            # Default site shift for manpower requirement
            shift = SiteShift.objects.filter(site=site).first()
            if not shift:
                dur = int(line.shift_hours * 60) if line.shift_hours else 480
                shift = SiteShift.objects.create(
                    site=site,
                    shift_code='DAY',
                    shift_name='Day Shift',
                    start_time='08:00',
                    end_time='16:00',
                    duration_minutes=dur,
                    is_active=True
                )

            # Manpower requirement
            mpr = SiteManpowerRequirement.objects.create(
                site=site,
                shift=shift,
                post_type=pt,
                required_count=line.headcount,
                effective_from=sr.start_date if sr else date.today(),
                is_active=True,
                created_by_user_id=actor_user.user_id
            )
            mpr_ids.append(str(mpr.requirement_id))

        generated['rate_ids'] = rate_ids
        generated['mpr_ids'] = mpr_ids
        conv.generated_records = generated
        conv.conversion_status = 'completed'
        conv.completed_at = timezone.now()
        conv.save()

        quotation.status = 'converted'
        quotation.save()

        if sr:
            sr.status = 'converted'
            sr.save()

    write_audit_event(
        action_code='quotation.converted',
        actor_user=actor_user,
        module='service_quotation',
        record_type='QUOTATION_CONVERSION',
        record_id=str(conv.conversion_id),
        new_values={'conversion_ref': conv_ref, 'status': 'completed'},
        reason=f"Converted accepted quotation {quotation.quotation_no} to Module 2 draft master records",
        request=request
    )
    return conv

