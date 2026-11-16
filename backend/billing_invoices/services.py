import hashlib
import json
import logging
import uuid
from datetime import date, datetime, timedelta
from decimal import Decimal, ROUND_HALF_UP, ROUND_HALF_EVEN, ROUND_CEILING, ROUND_FLOOR
from django.db import transaction
from django.utils import timezone
from django.core.exceptions import ValidationError

from .models import (
    InvoiceSettings,
    ClientBillingSettings,
    InvoiceNumberSequence,
    ClientInvoice,
    InvoiceLine,
    ClientPayment,
    ClientPaymentDeduction,
    InvoiceAttendanceAnnexure,
    InvoiceQueryLink,
    InvoiceReminder
)
from master_data.models import Client, ClientSite, ClientContact, ClientBillingRate
from attendance.models import AttendanceRecord, AttendancePeriod
from foundation.services.audit_service import write_audit_event
from foundation.services.notification_service import send_notification

logger = logging.getLogger(__name__)


# ----------------------------------------------------------------------------
# Helper: Indian Currency Number to Words (PRD 6.9, FR-11.116)
# ----------------------------------------------------------------------------
def number_to_indian_words(amount_dec: Decimal) -> str:
    """
    Converts a Decimal monetary amount to words using Indian digit grouping (Lakhs, Crores).
    Example: 33000.00 -> 'Rupees Thirty-Three Thousand Only'
    """
    if amount_dec is None:
        return ""
    
    amount = float(amount_dec)
    is_negative = amount < 0
    amount = abs(amount)

    ones = ["", "One", "Two", "Three", "Four", "Five", "Six", "Seven", "Eight", "Nine",
            "Ten", "Eleven", "Twelve", "Thirteen", "Fourteen", "Fifteen", "Sixteen",
            "Seventeen", "Eighteen", "Nineteen"]
    tens = ["", "", "Twenty", "Thirty", "Forty", "Fifty", "Sixty", "Seventy", "Eighty", "Ninety"]

    def two_digits(n):
        if n < 20:
            return ones[n]
        return tens[n // 10] + ("-" + ones[n % 10] if (n % 10 != 0) else "")

    def three_digits(n):
        h = n // 100
        rem = n % 100
        res = ""
        if h > 0:
            res += ones[h] + " Hundred"
            if rem > 0:
                res += " and "
        if rem > 0:
            res += two_digits(rem)
        return res

    integer_part = int(amount)
    fraction_part = int(round((amount - integer_part) * 100))

    if integer_part == 0:
        words = "Zero Rupees"
    else:
        crore = integer_part // 10000000
        rem_crore = integer_part % 10000000

        lakh = rem_crore // 100000
        rem_lakh = rem_crore % 100000

        thousand = rem_lakh // 1000
        rem_thousand = rem_lakh % 1000

        hundred = rem_thousand

        parts = []
        if crore > 0:
            parts.append(two_digits(crore) + " Crore")
        if lakh > 0:
            parts.append(two_digits(lakh) + " Lakh")
        if thousand > 0:
            parts.append(two_digits(thousand) + " Thousand")
        if hundred > 0:
            parts.append(three_digits(hundred))

        words = "Rupees " + " ".join(parts)

    if fraction_part > 0:
        words += " and " + two_digits(fraction_part) + " Paise"

    words += " Only"
    return ("Minus " if is_negative else "") + words


class BillingCalculationService:
    """
    Core billing calculation engine: rate resolution, attendance-to-post mapping,
    reliever deduplication, mid-month rate splits, exact decimals, and snapshots.
    """

    @staticmethod
    def get_company_settings(company_id):
        settings = InvoiceSettings.objects.filter(company_id=company_id).first()
        if not settings:
            settings = InvoiceSettings.objects.create(
                company_id=company_id,
                invoice_prefix='INV',
                number_format='{PREFIX}/{FY}/{SEQ:04d}',
                financial_year_start_month=4,
                financial_year_start_day=1,
                next_sequence=1,
                default_tax_label='GST',
                default_tax_percentage=Decimal('18.00'),
                rounding_method='ROUND_HALF_UP',
                rounding_level='TOTAL',
                default_payment_terms_days=30,
                effective_from=date.today()
            )
        return settings

    @staticmethod
    def get_client_settings(company_id, client_id, site_id=None):
        # 1. Site override if exists
        if site_id:
            site_settings = ClientBillingSettings.objects.filter(
                company_id=company_id,
                client_id=client_id,
                site_id=site_id,
                is_active=True
            ).first()
            if site_settings:
                return site_settings

        # 2. Client default settings
        return ClientBillingSettings.objects.filter(
            company_id=company_id,
            client_id=client_id,
            site_id__isnull=True,
            is_active=True
        ).first()

    @staticmethod
    def resolve_rate(client_id, site_id, post_type_id, duty_date):
        """
        Resolves effective-dated billing rate on duty_date.
        Site rate overrides client default (PRD 8.9, AC-11.3, AC-11.4).
        """
        # Site rate check
        if site_id:
            site_rate = ClientBillingRate.objects.filter(
                client_id=client_id,
                site_id=site_id,
                post_type_id=post_type_id,
                is_active=True,
                effective_from__lte=duty_date
            ).filter(
                models_q_effective_to(duty_date)
            ).order_by('-effective_from').first()
            if site_rate:
                return site_rate, 'SITE_OVERRIDE'

        # Client default rate check
        client_rate = ClientBillingRate.objects.filter(
            client_id=client_id,
            site_id__isnull=True,
            post_type_id=post_type_id,
            is_active=True,
            effective_from__lte=duty_date
        ).filter(
            models_q_effective_to(duty_date)
        ).order_by('-effective_from').first()
        if client_rate:
            return client_rate, 'CLIENT_DEFAULT'

        return None, None

    @staticmethod
    def preview_client_billing(company_id, client_id, period_start, period_end, is_unlocked_period_override=False, unlocked_period_reason=None):
        """
        Calculates eligible quantities and amounts for a client without saving to DB.
        Returns preview data and potential skip reason.
        """
        client = Client.objects.filter(client_id=client_id, company_id=company_id).first()
        if not client:
            return None, "Client not found."

        # 1. Client settings check (AC-11.1)
        client_settings = BillingCalculationService.get_client_settings(company_id, client_id)
        if not client_settings:
            return None, "Missing client billing settings (PRD 6.2, AC-11.1)."

        # 2. Locked attendance period check (AC-11.6, AC-11.7)
        periods = AttendancePeriod.objects.filter(
            company_id=company_id,
            start_date__lte=period_end,
            end_date__gte=period_start
        )
        has_unlocked = any((p.status or '').lower() != 'locked' for p in periods)
        if has_unlocked and not is_unlocked_period_override:
            return None, "Attendance period is not locked (PRD 6.4, AC-11.6)."
        if has_unlocked and is_unlocked_period_override and not unlocked_period_reason:
            return None, "Mandatory reason required for unlocked-period billing run (PRD 6.4, AC-11.7)."

        # 3. Retrieve eligible sites
        client_sites = ClientSite.objects.filter(client=client, operational_status='active')
        if not client_sites.exists():
            return None, "Client has no active sites."

        # 4. Fetch attendance records
        att_qs = AttendanceRecord.objects.filter(
            company_id=company_id,
            site_id__in=[s.site_id for s in client_sites],
            duty_date__gte=period_start,
            duty_date__lte=period_end,
            status__in=['approved', 'completed', 'PRESENT', 'HALF_DAY']
        )

        lines_preview = []
        annexure_items = []
        subtotal = Decimal('0.00')
        missing_rate_errors = []
        snapshot_records = []

        from deployment_roster.models import RosterAssignment

        # Group attendance by (site, post_type)
        grouped_att = {}
        for att in att_qs:
            post_type_id = None
            if att.assignment and hasattr(att.assignment, 'post_type_id'):
                post_type_id = att.assignment.post_type_id
            elif getattr(att, 'assignment_id', None):
                asg = RosterAssignment.objects.filter(assignment_id=att.assignment_id).first()
                if asg:
                    post_type_id = asg.post_type_id

            # Fallback to post_type from employee or first client rate post type if needed
            if not post_type_id:
                fallback_rate = ClientBillingRate.objects.filter(client_id=client_id, is_active=True).first()
                if fallback_rate:
                    post_type_id = fallback_rate.post_type_id

            key = (att.site_id, post_type_id)
            grouped_att.setdefault(key, []).append(att)

        for (site_id, post_type_id), att_list in grouped_att.items():
            site = next((s for s in client_sites if s.site_id == site_id), None)
            site_name = site.site_name if site else "Security Site"

            # Reliever / replacement mapping: group by (slot_id, duty_date)
            # If multiple guards cover same slot on duty_date, count ONCE (PRD 8.5, AC-11.11)
            slot_duty_map = {}
            for a in att_list:
                slot_id = None
                if a.assignment and hasattr(a.assignment, 'slot_id') and a.assignment.slot_id:
                    slot_id = a.assignment.slot_id
                elif getattr(a, 'assignment_id', None):
                    asg = RosterAssignment.objects.filter(assignment_id=a.assignment_id).first()
                    if asg and asg.slot_id:
                        slot_id = asg.slot_id
                slot_key = (slot_id or a.attendance_id, a.duty_date)
                if slot_key not in slot_duty_map:
                    slot_duty_map[slot_key] = a
                else:
                    # Duplicate reliever on same slot
                    annexure_items.append({
                        'site_id': site_id,
                        'duty_date': a.duty_date,
                        'shift_id': a.shift_id,
                        'post_type_id': post_type_id,
                        'guard_id': a.employee_id,
                        'coverage_status': 'REPLACEMENT',
                        'is_manual': a.is_manual,
                        'regular_minutes': a.regular_minutes,
                        'overtime_minutes': a.overtime_minutes,
                        'is_billed': False, # Already billed via original slot holder
                        'deduction_applied': False
                    })

            # For each covered unique slot duty date, resolve rate
            dates_by_rate = {}
            for (slot_id, duty_date), primary_att in slot_duty_map.items():
                rate_obj, rate_source = BillingCalculationService.resolve_rate(client_id, site_id, post_type_id, duty_date)
                if not rate_obj:
                    missing_rate_errors.append(f"Missing billing rate for site '{site_name}' on date {duty_date} (AC-11.4).")
                    continue

                rate_key = (rate_obj.rate_id, rate_obj.rate_amount, rate_obj.rate_type, rate_obj.effective_from, rate_obj.effective_to)
                dates_by_rate.setdefault(rate_key, []).append((duty_date, primary_att))

            # Generate split lines for each distinct rate period (PRD 8.9, AC-11.13)
            for (rate_id, rate_amount, rate_type, eff_start, eff_end), date_att_pairs in dates_by_rate.items():
                qty = Decimal(str(len(date_att_pairs)))
                line_amt = (qty * rate_amount).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
                subtotal += line_amt

                desc = f"Security Guard Services - {site_name} ({len(date_att_pairs)} shifts/days @ ₹{rate_amount})"
                lines_preview.append({
                    'site_id': site_id,
                    'site_name': site_name,
                    'post_type_id': post_type_id,
                    'description': desc,
                    'source_type': 'ATTENDANCE',
                    'quantity': qty,
                    'unit': 'PER_DAY' if (rate_type or '').upper() == 'DAILY' else 'PER_SHIFT' if (rate_type or '').upper() == 'SHIFT' else 'PER_MONTH',
                    'unit_rate': rate_amount,
                    'tax_rate': Decimal('18.00'),
                    'line_amount': line_amt,
                    'effective_rate_start': eff_start,
                    'effective_rate_end': eff_end,
                })

                for d_date, a_rec in date_att_pairs:
                    annexure_items.append({
                        'site_id': site_id,
                        'duty_date': d_date,
                        'shift_id': a_rec.shift_id,
                        'post_type_id': post_type_id,
                        'guard_id': a_rec.employee_id,
                        'coverage_status': 'COVERED',
                        'is_manual': a_rec.is_manual,
                        'regular_minutes': a_rec.regular_minutes,
                        'overtime_minutes': a_rec.overtime_minutes,
                        'is_billed': True,
                        'deduction_applied': False
                    })

                snapshot_records.append({
                    'site_id': str(site_id),
                    'post_type_id': str(post_type_id) if post_type_id else None,
                    'rate_id': str(rate_id),
                    'rate_amount': str(rate_amount),
                    'count': len(date_att_pairs)
                })

        if missing_rate_errors:
            return None, "; ".join(missing_rate_errors)

        if not lines_preview:
            return None, "No billable attendance records found in selected period."

        # Tax calculation
        company_settings = BillingCalculationService.get_company_settings(company_id)
        tax_pct = client_settings.tax_percentage if (client_settings.tax_override_enabled and client_settings.tax_percentage is not None) else company_settings.default_tax_percentage
        tax_amt = (subtotal * (tax_pct / Decimal('100.00'))).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        total_amt = (subtotal + tax_amt).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

        preview_data = {
            'client_id': client_id,
            'client_name': client.legal_name or client.display_name,
            'period_start': period_start,
            'period_end': period_end,
            'lines': lines_preview,
            'annexures': annexure_items,
            'subtotal': subtotal,
            'taxable_amount': subtotal,
            'tax_percentage': tax_pct,
            'tax_amount': tax_amt,
            'total_amount': total_amt,
            'snapshot': snapshot_records
        }
        return preview_data, None


def models_q_effective_to(target_date):
    from django.db.models import Q
    return Q(effective_to__isnull=True) | Q(effective_to__gte=target_date)


class BillingRunService:
    """
    Manages billing runs, draft generation, idempotency, skipped-client reports,
    and draft refreshes upon source corrections.
    """

    @staticmethod
    def run_billing(company_id, period_start, period_end, client_ids=None, user=None, is_unlocked_period_override=False, unlocked_period_reason=None):
        """
        Executes a billing run for selected or all clients.
        Idempotent: refreshes existing Drafts; never alters issued/paid/cancelled invoices (PRD 6.4, AC-11.8, AC-11.9).
        """
        if not client_ids:
            clients = Client.objects.filter(company_id=company_id, status='active')
        else:
            clients = Client.objects.filter(company_id=company_id, client_id__in=client_ids)

        drafts_created = []
        drafts_refreshed = []
        skipped_clients = []

        for client in clients:
            preview_data, skip_reason = BillingCalculationService.preview_client_billing(
                company_id=company_id,
                client_id=client.client_id,
                period_start=period_start,
                period_end=period_end,
                is_unlocked_period_override=is_unlocked_period_override,
                unlocked_period_reason=unlocked_period_reason
            )

            if skip_reason:
                skipped_clients.append({
                    'client_id': str(client.client_id),
                    'client_name': client.legal_name or client.display_name,
                    'reason': skip_reason
                })
                continue

            # Check if invoice exists for this client and period (AC-11.8, AC-11.9)
            existing_invoice = ClientInvoice.objects.filter(
                company_id=company_id,
                client_id=client.client_id,
                period_start=period_start,
                period_end=period_end
            ).first()

            if existing_invoice:
                if existing_invoice.is_issued:
                    # Sent, Partially Paid, Paid, or Cancelled invoices are NEVER modified (AC-11.9)
                    continue
                else:
                    # Refresh existing draft (AC-11.8, AC-11.24)
                    BillingRunService._apply_preview_to_draft(existing_invoice, preview_data, user)
                    drafts_refreshed.append(existing_invoice)
            else:
                # Create fresh draft
                draft_ref = f"DFT-{period_start.strftime('%Y%m')}-{client.client_code or 'CL'}-{uuid.uuid4().hex[:4].upper()}"
                new_draft = ClientInvoice.objects.create(
                    company_id=company_id,
                    client_id=client.client_id,
                    draft_reference=draft_ref,
                    period_start=period_start,
                    period_end=period_end,
                    status='DRAFT',
                    subtotal=preview_data['subtotal'],
                    taxable_amount=preview_data['taxable_amount'],
                    tax_amount=preview_data['tax_amount'],
                    total_amount=preview_data['total_amount'],
                    outstanding_amount=preview_data['total_amount'],
                    source_snapshot={'sources': preview_data['snapshot']},
                    source_changed=False,
                    is_unlocked_period_override=is_unlocked_period_override,
                    unlocked_period_reason=unlocked_period_reason,
                    created_by=user.user_id if user else None
                )

                # Create lines
                for l in preview_data['lines']:
                    InvoiceLine.objects.create(
                        invoice_id=new_draft.invoice_id,
                        site_id=l['site_id'],
                        post_type_id=l['post_type_id'],
                        description=l['description'],
                        source_type=l['source_type'],
                        quantity=l['quantity'],
                        unit=l['unit'],
                        unit_rate=l['unit_rate'],
                        tax_rate=l['tax_rate'],
                        line_amount=l['line_amount'],
                        effective_rate_start=l['effective_rate_start'],
                        effective_rate_end=l['effective_rate_end']
                    )

                # Create annexure items
                for a in preview_data['annexures']:
                    InvoiceAttendanceAnnexure.objects.create(
                        invoice_id=new_draft.invoice_id,
                        site_id=a['site_id'],
                        duty_date=a['duty_date'],
                        shift_id=a['shift_id'],
                        post_type_id=a['post_type_id'],
                        guard_id=a['guard_id'],
                        coverage_status=a['coverage_status'],
                        is_manual=a['is_manual'],
                        regular_minutes=a['regular_minutes'],
                        overtime_minutes=a['overtime_minutes'],
                        is_billed=a['is_billed'],
                        deduction_applied=a['deduction_applied']
                    )

                drafts_created.append(new_draft)

        return {
            'drafts_created': len(drafts_created),
            'drafts_refreshed': len(drafts_refreshed),
            'skipped_clients': skipped_clients
        }

    @staticmethod
    def _apply_preview_to_draft(draft: ClientInvoice, preview_data: dict, user):
        """
        Refreshes lines and annexures for an existing draft.
        """
        InvoiceLine.objects.filter(invoice_id=draft.invoice_id, source_type='ATTENDANCE').delete()
        InvoiceAttendanceAnnexure.objects.filter(invoice_id=draft.invoice_id).delete()

        # Recalculate manual lines if any
        manual_lines = InvoiceLine.objects.filter(invoice_id=draft.invoice_id, source_type='MANUAL')
        manual_subtotal = sum(ml.line_amount for ml in manual_lines)

        for l in preview_data['lines']:
            InvoiceLine.objects.create(
                invoice_id=draft.invoice_id,
                site_id=l['site_id'],
                post_type_id=l['post_type_id'],
                description=l['description'],
                source_type=l['source_type'],
                quantity=l['quantity'],
                unit=l['unit'],
                unit_rate=l['unit_rate'],
                tax_rate=l['tax_rate'],
                line_amount=l['line_amount'],
                effective_rate_start=l['effective_rate_start'],
                effective_rate_end=l['effective_rate_end']
            )

        for a in preview_data['annexures']:
            InvoiceAttendanceAnnexure.objects.create(
                invoice_id=draft.invoice_id,
                site_id=a['site_id'],
                duty_date=a['duty_date'],
                shift_id=a['shift_id'],
                post_type_id=a['post_type_id'],
                guard_id=a['guard_id'],
                coverage_status=a['coverage_status'],
                is_manual=a['is_manual'],
                regular_minutes=a['regular_minutes'],
                overtime_minutes=a['overtime_minutes'],
                is_billed=a['is_billed'],
                deduction_applied=a['deduction_applied']
            )

        new_subtotal = preview_data['subtotal'] + manual_subtotal
        company_settings = BillingCalculationService.get_company_settings(draft.company_id)
        tax_pct = preview_data['tax_percentage']
        tax_amt = (new_subtotal * (tax_pct / Decimal('100.00'))).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        total_amt = (new_subtotal + tax_amt).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

        draft.subtotal = new_subtotal
        draft.taxable_amount = new_subtotal
        draft.tax_amount = tax_amt
        draft.total_amount = total_amt
        draft.outstanding_amount = total_amt
        draft.source_snapshot = {'sources': preview_data['snapshot']}
        draft.source_changed = False
        draft.source_change_details = {}
        draft.save()


class InvoiceManagementService:
    """
    Manages manual adjustments, annexure reconciliation, invoice issuing,
    PDF hash generation, cancellation, and replacement.
    """

    @staticmethod
    def add_manual_line(invoice_id, data, user):
        invoice = ClientInvoice.objects.get(invoice_id=invoice_id)
        if invoice.is_issued:
            raise ValidationError("Issued invoices are immutable. Cannot add manual lines (PRD 6.8, AC-11.37).")

        unit_rate = data['unit_rate']
        quantity = data.get('quantity', Decimal('1.00'))
        is_neg = data.get('is_negative', False)
        amt = (quantity * unit_rate).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        if is_neg:
            amt = -abs(amt)

        line = InvoiceLine.objects.create(
            invoice_id=invoice.invoice_id,
            site_id=data.get('site_id'),
            description=data['description'],
            source_type='MANUAL',
            quantity=quantity,
            unit=data.get('unit', 'MANUAL'),
            unit_rate=unit_rate,
            tax_rate=data.get('tax_rate', Decimal('18.00')),
            line_amount=amt,
            manual_reason=data['manual_reason'],
            client_visible_description=data.get('client_visible_description') or data['description'],
            is_negative=is_neg
        )

        # Recalculate totals
        all_lines = InvoiceLine.objects.filter(invoice_id=invoice.invoice_id)
        subtotal = sum(l.line_amount for l in all_lines)
        company_settings = BillingCalculationService.get_company_settings(invoice.company_id)
        tax_amt = (subtotal * (company_settings.default_tax_percentage / Decimal('100.00'))).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        total_amt = subtotal + tax_amt

        invoice.subtotal = subtotal
        invoice.taxable_amount = subtotal
        invoice.tax_amount = tax_amt
        invoice.total_amount = total_amt
        invoice.outstanding_amount = total_amt
        invoice.save()
        return line

    @staticmethod
    def verify_annexure_reconciliation(invoice: ClientInvoice):
        """
        Reconciles billed attendance quantities with annexure records.
        Blocks issue if there is a mismatch (PRD 6.13, 8.11, AC-11.41 to AC-11.43).
        """
        billed_qty = sum(
            l.quantity for l in InvoiceLine.objects.filter(invoice_id=invoice.invoice_id, source_type='ATTENDANCE')
        )
        annexure_billed_count = InvoiceAttendanceAnnexure.objects.filter(
            invoice_id=invoice.invoice_id,
            is_billed=True
        ).count()

        if billed_qty != Decimal(str(annexure_billed_count)):
            raise ValidationError(
                f"Annexure reconciliation mismatch: Billed quantity ({billed_qty}) does not match annexure billed items ({annexure_billed_count}). Issue blocked (AC-11.43)."
            )
        return True

    @staticmethod
    def issue_invoice(invoice_id, user):
        """
        Issues an eligible draft atomically.
        Allocates next sequential number with row lock, sets invoice date/due date,
        generates PDF hash, locks record, and transitions status to SENT (PRD 6.8, AC-11.33 to AC-11.36).
        """
        with transaction.atomic():
            invoice = ClientInvoice.objects.select_for_update().get(invoice_id=invoice_id)
            if invoice.status not in ['DRAFT', 'PENDING_APPROVAL']:
                raise ValidationError("Only Draft or Pending Approval invoices can be issued.")

            if invoice.source_changed:
                raise ValidationError("Source data changed. Refresh draft before issuing (PRD 6.6, AC-11.22).")

            # Verify annexure reconciliation (AC-11.43)
            InvoiceManagementService.verify_annexure_reconciliation(invoice)

            # Check second admin approval if required
            settings = BillingCalculationService.get_company_settings(invoice.company_id)
            if settings.second_admin_approval_required and invoice.total_amount >= settings.second_admin_approval_threshold:
                if not invoice.approved_by:
                    invoice.status = 'PENDING_APPROVAL'
                    invoice.save()
                    return invoice

            # Allocate sequential invoice number atomically
            fy = InvoiceManagementService._get_financial_year(settings)
            seq_record, _ = InvoiceNumberSequence.objects.select_for_update().get_or_create(
                company_id=invoice.company_id,
                series_code='DEFAULT',
                financial_year=fy,
                defaults={'last_number': 0}
            )
            seq_record.last_number += 1
            seq_record.save()

            inv_no = settings.number_format.replace('{PREFIX}', settings.invoice_prefix)\
                                           .replace('{FY}', fy)\
                                           .replace('{SEQ:04d}', f"{seq_record.last_number:04d}")

            today = date.today()
            client_settings = BillingCalculationService.get_client_settings(invoice.company_id, invoice.client_id)
            terms = client_settings.payment_terms_days if client_settings else settings.default_payment_terms_days
            due = today + timedelta(days=terms)

            # Generate synthetic PDF content and cryptographic SHA-256 hash
            pdf_hash = InvoiceManagementService._generate_pdf_hash(invoice, inv_no, today, due)

            invoice.invoice_no = inv_no
            invoice.invoice_date = today
            invoice.due_date = due
            invoice.status = 'SENT'
            invoice.pdf_hash = pdf_hash
            invoice.pdf_file_reference = f"invoices/{invoice.company_id}/{inv_no}.pdf"
            invoice.issued_by = user.user_id if user else None
            invoice.issued_at = timezone.now()
            invoice.save()

            # Audit log
            if user:
                write_audit_event(
                    action_code='INVOICE_ISSUED',
                    actor_user=user,
                    module='billing_invoices',
                    record_type='ClientInvoice',
                    record_id=str(invoice.invoice_id),
                    new_values={'invoice_no': inv_no, 'total': str(invoice.total_amount)},
                    company_id=invoice.company_id
                )

            return invoice

    @staticmethod
    def cancel_invoice(invoice_id, cancelled_reason, client_visible_reason=None, user=None):
        """
        Cancels an issued invoice.
        Blocked if recorded payments exist (PRD 6.10, AC-11.53).
        """
        invoice = ClientInvoice.objects.get(invoice_id=invoice_id)
        if not invoice.is_issued:
            raise ValidationError("Only issued invoices can be cancelled.")

        # Check payments (AC-11.53)
        active_payments = ClientPayment.objects.filter(invoice_id=invoice_id, status='ACTIVE').exists()
        if active_payments:
            raise ValidationError("Invoice has active payments. Payments must be reversed before cancellation (AC-11.53).")

        invoice.status = 'CANCELLED'
        invoice.cancelled_reason = cancelled_reason
        invoice.client_visible_cancellation_reason = client_visible_reason or 'Invoice cancelled by administration.'
        invoice.cancelled_by = user.user_id if user else None
        invoice.cancelled_at = timezone.now()
        invoice.save()
        return invoice

    @staticmethod
    def create_replacement_draft(invoice_id, user=None):
        """
        Creates a new draft replacement linked to a cancelled invoice (PRD 6.10, AC-11.40).
        """
        original = ClientInvoice.objects.get(invoice_id=invoice_id)
        if original.status != 'CANCELLED':
            raise ValidationError("Replacements can only be created from cancelled invoices.")

        # Generate fresh draft for the same period
        preview_data, skip_reason = BillingCalculationService.preview_client_billing(
            company_id=original.company_id,
            client_id=original.client_id,
            period_start=original.period_start,
            period_end=original.period_end
        )
        if skip_reason:
            raise ValidationError(f"Cannot generate replacement draft: {skip_reason}")

        draft_ref = f"DFT-REPL-{original.period_start.strftime('%Y%m')}-{uuid.uuid4().hex[:4].upper()}"
        replacement = ClientInvoice.objects.create(
            company_id=original.company_id,
            client_id=original.client_id,
            draft_reference=draft_ref,
            period_start=original.period_start,
            period_end=original.period_end,
            status='DRAFT',
            subtotal=preview_data['subtotal'],
            taxable_amount=preview_data['taxable_amount'],
            tax_amount=preview_data['tax_amount'],
            total_amount=preview_data['total_amount'],
            outstanding_amount=preview_data['total_amount'],
            original_invoice_id=original.invoice_id,
            source_snapshot={'sources': preview_data['snapshot']},
            created_by=user.user_id if user else None
        )

        for l in preview_data['lines']:
            InvoiceLine.objects.create(
                invoice_id=replacement.invoice_id,
                site_id=l['site_id'],
                post_type_id=l['post_type_id'],
                description=l['description'],
                source_type=l['source_type'],
                quantity=l['quantity'],
                unit=l['unit'],
                unit_rate=l['unit_rate'],
                tax_rate=l['tax_rate'],
                line_amount=l['line_amount'],
                effective_rate_start=l['effective_rate_start'],
                effective_rate_end=l['effective_rate_end']
            )

        for a in preview_data['annexures']:
            InvoiceAttendanceAnnexure.objects.create(
                invoice_id=replacement.invoice_id,
                site_id=a['site_id'],
                duty_date=a['duty_date'],
                shift_id=a['shift_id'],
                post_type_id=a['post_type_id'],
                guard_id=a['guard_id'],
                coverage_status=a['coverage_status'],
                is_manual=a['is_manual'],
                regular_minutes=a['regular_minutes'],
                overtime_minutes=a['overtime_minutes'],
                is_billed=a['is_billed'],
                deduction_applied=a['deduction_applied']
            )

        original.replacement_invoice_id = replacement.invoice_id
        original.save()
        return replacement

    @staticmethod
    def _get_financial_year(settings: InvoiceSettings) -> str:
        today = date.today()
        # Indian FY: starts in April (e.g., April 2026 -> 2026-27)
        if today.month >= settings.financial_year_start_month:
            y1 = today.year
            y2 = (today.year + 1) % 100
        else:
            y1 = today.year - 1
            y2 = today.year % 100
        return f"{y1}-{y2:02d}"

    @staticmethod
    def _generate_pdf_hash(invoice, inv_no, inv_date, due_date) -> str:
        payload = f"{invoice.company_id}|{invoice.client_id}|{inv_no}|{inv_date}|{due_date}|{invoice.total_amount}"
        return hashlib.sha256(payload.encode('utf-8')).hexdigest()


class PaymentReceivablesService:
    """
    Handles payment recording, TDS & client deductions, payment reversals,
    overpayments, ageing buckets, query linking, and CSV exports.
    """

    @staticmethod
    def record_payment(invoice_id, data, user=None):
        """
        Records a client payment against an invoice.
        Updates outstanding balance, tracks TDS / other deductions, and checks overpayments (PRD 6.11, AC-11.45 to AC-11.53).
        """
        with transaction.atomic():
            invoice = ClientInvoice.objects.select_for_update().get(invoice_id=invoice_id)
            if not invoice.is_issued or invoice.status == 'CANCELLED':
                raise ValidationError("Payments can only be recorded against active issued invoices.")

            payment_amt = data['amount']
            tds_amt = data.get('tds_amount', Decimal('0.00'))
            other_amt = data.get('other_deduction_amount', Decimal('0.00'))
            other_reason = data.get('other_deduction_reason')

            total_credit = payment_amt + tds_amt + other_amt
            unallocated = Decimal('0.00')

            # Overpayment handling (PRD 6.11, AC-11.50)
            if total_credit > invoice.outstanding_amount:
                unallocated = total_credit - invoice.outstanding_amount

            payment = ClientPayment.objects.create(
                company_id=invoice.company_id,
                client_id=invoice.client_id,
                invoice_id=invoice.invoice_id,
                payment_date=data['payment_date'],
                amount=payment_amt,
                payment_method=data['payment_method'],
                reference_no=data.get('reference_no'),
                notes=data.get('notes'),
                status='ACTIVE',
                unallocated_amount=unallocated,
                created_by=user.user_id if user else None
            )

            # Record TDS deduction (AC-11.51)
            if tds_amt > 0:
                ClientPaymentDeduction.objects.create(
                    payment_id=payment.client_payment_id,
                    invoice_id=invoice.invoice_id,
                    deduction_type='TDS',
                    amount=tds_amt,
                    notes='Tax Deducted at Source'
                )

            # Record Other deduction (AC-11.52)
            if other_amt > 0:
                ClientPaymentDeduction.objects.create(
                    payment_id=payment.client_payment_id,
                    invoice_id=invoice.invoice_id,
                    deduction_type='OTHER',
                    amount=other_amt,
                    reason=other_reason,
                    notes=data.get('notes')
                )

            # Recalculate invoice balance
            PaymentReceivablesService._recalculate_invoice_balance(invoice)
            return payment

    @staticmethod
    def reverse_payment(payment_id, reversal_reason, user=None):
        """
        Reverses an incorrect payment with a mandatory reason (PRD 6.11, AC-11.49).
        Never directly edits or deletes payment records (AC-11.48).
        """
        with transaction.atomic():
            payment = ClientPayment.objects.select_for_update().get(client_payment_id=payment_id)
            if payment.status == 'REVERSED':
                raise ValidationError("Payment is already reversed.")

            payment.status = 'REVERSED'
            payment.reversal_reason = reversal_reason
            payment.reversed_at = timezone.now()
            payment.reversed_by = user.user_id if user else None
            payment.save()

            invoice = ClientInvoice.objects.select_for_update().get(invoice_id=payment.invoice_id)
            PaymentReceivablesService._recalculate_invoice_balance(invoice)
            return payment

    @staticmethod
    def _recalculate_invoice_balance(invoice: ClientInvoice):
        active_payments = ClientPayment.objects.filter(invoice_id=invoice.invoice_id, status='ACTIVE')
        paid_sum = sum(p.amount for p in active_payments)
        active_deductions = ClientPaymentDeduction.objects.filter(
            payment_id__in=[p.client_payment_id for p in active_payments]
        )
        deduction_sum = sum(d.amount for d in active_deductions)

        total_settled = paid_sum + deduction_sum
        outstanding = max(Decimal('0.00'), invoice.total_amount - total_settled)

        invoice.paid_amount = paid_sum
        invoice.deduction_amount = deduction_sum
        invoice.outstanding_amount = outstanding

        if outstanding == Decimal('0.00'):
            invoice.status = 'PAID'
            invoice.overdue_flag = False
        elif paid_sum > 0 or deduction_sum > 0:
            invoice.status = 'PARTIALLY_PAID'
        elif invoice.status != 'CANCELLED':
            invoice.status = 'SENT'

        # Check overdue flag
        if invoice.due_date and invoice.due_date < date.today() and invoice.outstanding_amount > 0 and invoice.status != 'CANCELLED':
            invoice.overdue_flag = True
        else:
            invoice.overdue_flag = False

        invoice.save()

    @staticmethod
    def get_dashboard_metrics(company_id):
        """
        Dashboard overview: billed this month, collected this month, outstanding, overdue (PRD 9.1 Screen 1).
        """
        today = date.today()
        month_start = today.replace(day=1)

        invoices_this_month = ClientInvoice.objects.filter(
            company_id=company_id,
            invoice_date__gte=month_start,
            status__in=['SENT', 'PARTIALLY_PAID', 'PAID']
        )
        billed_this_month = sum(i.total_amount for i in invoices_this_month)

        payments_this_month = ClientPayment.objects.filter(
            company_id=company_id,
            payment_date__gte=month_start,
            status='ACTIVE'
        )
        collected_this_month = sum(p.amount for p in payments_this_month)

        all_active_invoices = ClientInvoice.objects.filter(
            company_id=company_id,
            status__in=['SENT', 'PARTIALLY_PAID']
        )
        outstanding_total = sum(i.outstanding_amount for i in all_active_invoices)
        overdue_total = sum(i.outstanding_amount for i in all_active_invoices if i.due_date and i.due_date < today)

        return {
            'billed_this_month': billed_this_month,
            'collected_this_month': collected_this_month,
            'outstanding_total': outstanding_total,
            'overdue_total': overdue_total,
            'total_invoices_count': ClientInvoice.objects.filter(company_id=company_id).count(),
            'active_invoices_count': all_active_invoices.count()
        }

    @staticmethod
    def get_receivables_ageing(company_id):
        """
        Receivables by client and ageing buckets: Current, 1-30, 31-60, 61-90, 90+ (PRD 6.11, Screen 11).
        """
        today = date.today()
        invoices = ClientInvoice.objects.filter(
            company_id=company_id,
            status__in=['SENT', 'PARTIALLY_PAID']
        ).order_by('due_date')

        ageing_records = []
        buckets = {'current': Decimal('0.00'), '1_30': Decimal('0.00'), '31_60': Decimal('0.00'), '61_90': Decimal('0.00'), '90_plus': Decimal('0.00')}

        for inv in invoices:
            client = Client.objects.filter(client_id=inv.client_id).first()
            client_name = client.legal_name or client.display_name if client else "Unknown"
            days_overdue = (today - inv.due_date).days if inv.due_date and inv.due_date < today else 0

            if days_overdue <= 0:
                bucket_name = 'CURRENT'
                buckets['current'] += inv.outstanding_amount
            elif 1 <= days_overdue <= 30:
                bucket_name = '1_30'
                buckets['1_30'] += inv.outstanding_amount
            elif 31 <= days_overdue <= 60:
                bucket_name = '31_60'
                buckets['31_60'] += inv.outstanding_amount
            elif 61 <= days_overdue <= 90:
                bucket_name = '61_90'
                buckets['61_90'] += inv.outstanding_amount
            else:
                bucket_name = '90_PLUS'
                buckets['90_plus'] += inv.outstanding_amount

            ageing_records.append({
                'invoice_id': str(inv.invoice_id),
                'invoice_no': inv.invoice_no,
                'client_id': str(inv.client_id),
                'client_name': client_name,
                'invoice_date': inv.invoice_date,
                'due_date': inv.due_date,
                'total_amount': inv.total_amount,
                'outstanding_amount': inv.outstanding_amount,
                'days_overdue': days_overdue,
                'ageing_bucket': bucket_name,
                'under_query_flag': inv.under_query_flag
            })

        return {
            'buckets': buckets,
            'invoices': ageing_records
        }

    @staticmethod
    def link_invoice_query(invoice_id, ticket_id, client_id, query_category='INVOICE_QUERY'):
        """
        Links an invoice to a Module 8 ticket and flags it Under Query (PRD 10.4, AC-11.54, AC-11.55).
        Pauses payment reminders.
        """
        link = InvoiceQueryLink.objects.create(
            invoice_id=invoice_id,
            ticket_id=ticket_id,
            client_id=client_id,
            query_category=query_category,
            status='OPEN'
        )
        invoice = ClientInvoice.objects.get(invoice_id=invoice_id)
        invoice.under_query_flag = True
        invoice.save()

        # Pause active reminders (AC-11.55)
        InvoiceReminder.objects.filter(invoice_id=invoice_id, status='SENT').update(status='PAUSED_UNDER_QUERY')
        return link

    @staticmethod
    def close_invoice_query(ticket_id):
        """
        Clears under_query_flag when all linked tickets are closed (PRD 10.4, AC-11.57).
        """
        link = InvoiceQueryLink.objects.filter(ticket_id=ticket_id).first()
        if not link:
            return
        link.status = 'CLOSED'
        link.closed_at = timezone.now()
        link.save()

        # Check if other open queries remain
        remaining_open = InvoiceQueryLink.objects.filter(invoice_id=link.invoice_id, status='OPEN').exists()
        if not remaining_open:
            invoice = ClientInvoice.objects.get(invoice_id=link.invoice_id)
            invoice.under_query_flag = False
            invoice.save()
            # Reminders can resume
            InvoiceReminder.objects.filter(invoice_id=link.invoice_id, status='PAUSED_UNDER_QUERY').update(status='SENT')
