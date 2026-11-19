import hashlib
import json
import uuid
from decimal import Decimal
from datetime import datetime, date, timedelta
from calendar import monthrange
from django.utils import timezone
from django.db import transaction
from rest_framework.exceptions import ValidationError, PermissionDenied, NotFound

from guard_management.models import Employee
from attendance.models import AttendancePeriod, AttendanceRecord
from master_data.models import ClientSite
from .models import (
    SalaryComponent, SalaryStructure, SalaryStructureLine,
    GuardSalaryAssignment, MinimumWage, PaidDayRuleSet,
    WeeklyOffCalendar, StatutoryRuleSet, Advance,
    AdvanceLedgerEntry, ManualDeduction, PayrollRun,
    PayrollResult, PayrollResultLine, Payslip,
    PaymentRecord, FinalSettlement, StatutoryPayment
)


def get_pre_run_checklist(company_id, period_start, period_end):
    """
    Evaluates prerequisites before payroll execution (PRD 6.7, Screen 11).
    Checks attendance lock, missing structures, minimum wage breaches, missing bank details.
    """
    if isinstance(period_start, str):
        period_start = datetime.strptime(period_start, "%Y-%m-%d").date()
    if isinstance(period_end, str):
        period_end = datetime.strptime(period_end, "%Y-%m-%d").date()

    # 1. Attendance Period Lock Check (AC14.9, AC14.10)
    locked_period_exists = AttendancePeriod.objects.filter(
        company_id=company_id,
        start_date__lte=period_start,
        end_date__gte=period_end,
        status='locked'
    ).exists()

    # 2. Eligible Guards
    guards = Employee.objects.filter(
        company_id=company_id,
        date_joined__lte=period_end
    ).exclude(employment_status='terminated', exit_date__lt=period_start)

    total_eligible = guards.count()

    # 3. Missing Salary Structures (AC14.6)
    missing_structures = []
    # 4. Missing Bank Details (AC14.45)
    missing_bank_details = []
    # 5. Missing Statutory Identifiers (AC14.19)
    missing_statutory_ids = []

    for g in guards:
        has_assignment = GuardSalaryAssignment.objects.filter(
            guard_id=g.employee_id,
            status='ACTIVE',
            effective_from__lte=period_end
        ).filter(
            models_condition_assignment(period_start)
        ).exists()

        if not has_assignment:
            missing_structures.append({
                "guard_id": str(g.employee_id),
                "employee_code": g.employee_code,
                "name": f"{g.first_name} {g.last_name or ''}".strip(),
                "issue": "No active salary structure assignment overlapping this period"
            })

        bank_info = g.bank_details or {}
        if not bank_info.get('account_number') and not getattr(g, 'bank_account_number', None):
            missing_bank_details.append({
                "guard_id": str(g.employee_id),
                "employee_code": g.employee_code,
                "name": f"{g.first_name} {g.last_name or ''}".strip(),
                "issue": "Missing bank account number or IFSC"
            })

        if not g.pan_number and not g.uan_number and not g.esi_number:
            missing_statutory_ids.append({
                "guard_id": str(g.employee_id),
                "employee_code": g.employee_code,
                "name": f"{g.first_name} {g.last_name or ''}".strip(),
                "issue": "No PAN, UAN, or ESI number on file"
            })

    # 6. Unapproved Overtime (AC14.11)
    unapproved_ot_records = AttendanceRecord.objects.filter(
        company_id=company_id,
        duty_date__gte=period_start,
        duty_date__lte=period_end,
        overtime_minutes__gt=0
    ).exclude(status='approved').count()

    # 7. Minimum Wage Configurations
    min_wage_count = MinimumWage.objects.filter(company_id=company_id).count()

    # 8. Active Runs for this Period (AC14.34)
    period_ref = f"{period_start.year}-{str(period_start.month).zfill(2)}"
    existing_active_runs = PayrollRun.objects.filter(
        company_id=company_id,
        period_reference=period_ref
    ).exclude(status='CANCELLED').count()

    can_proceed_final = locked_period_exists and len(missing_structures) == 0
    can_proceed_provisional = len(missing_structures) == 0

    return {
        "period_reference": period_ref,
        "period_start": str(period_start),
        "period_end": str(period_end),
        "total_eligible_guards": total_eligible,
        "attendance_locked": locked_period_exists,
        "run_type_recommendation": "FINAL" if locked_period_exists else "PROVISIONAL",
        "missing_salary_structures_count": len(missing_structures),
        "missing_salary_structures": missing_structures[:10],
        "missing_bank_details_count": len(missing_bank_details),
        "missing_bank_details": missing_bank_details[:10],
        "missing_statutory_ids_count": len(missing_statutory_ids),
        "unapproved_ot_records_count": unapproved_ot_records,
        "minimum_wage_rules_configured": min_wage_count > 0,
        "existing_active_runs_count": existing_active_runs,
        "can_proceed_final": can_proceed_final,
        "can_proceed_provisional": can_proceed_provisional,
        "blocking_reasons": (
            (["Attendance period is not locked. Run will be PROVISIONAL."] if not locked_period_exists else []) +
            ([f"{len(missing_structures)} guards lack active salary structures."] if missing_structures else [])
        )
    }


def models_condition_assignment(period_start):
    from django.db.models import Q
    return Q(effective_to__isnull=True) | Q(effective_to__gte=period_start)


def calculate_payroll_run(run_id, company_id, preparer_id):
    """
    Executes the full Section 8 calculation engine for a payroll run.
    Applies exact decimal arithmetic, attendance proration, overtime, statutory rules,
    manual deductions, advance ledger recovery, and net-pay zero floor.
    """
    try:
        run = PayrollRun.objects.get(run_id=run_id, company_id=company_id)
    except PayrollRun.DoesNotExist:
        raise NotFound("Payroll run not found.")

    if run.status in ['APPROVED', 'RELEASED', 'PAID', 'CLOSED']:
        raise ValidationError(f"Run {run.period_reference} is in status '{run.status}' and is immutable (AC14.31).")

    # Check Attendance Lock: If unlocked, forced to PROVISIONAL (AC14.10)
    is_locked = AttendancePeriod.objects.filter(
        company_id=company_id,
        start_date__lte=run.period_start,
        end_date__gte=run.period_end,
        status='locked'
    ).exists()

    if not is_locked:
        run.run_type = 'PROVISIONAL'

    # Clean existing draft results if recalculating
    PayrollResult.objects.filter(run=run).delete()

    # Determine Month Length Rule
    paid_day_rule = PaidDayRuleSet.objects.filter(company_id=company_id, status='ACTIVE').first()
    if paid_day_rule and paid_day_rule.month_length_rule == 'FIXED_26':
        month_length = Decimal('26.00')
    elif paid_day_rule and paid_day_rule.month_length_rule == 'FIXED_30':
        month_length = Decimal('30.00')
    else:
        # CALENDAR_DAYS
        num_days = monthrange(run.period_start.year, run.period_start.month)[1]
        month_length = Decimal(str(num_days))

    # Load Active Statutory Rule Sets
    stat_rules = list(StatutoryRuleSet.objects.filter(company_id=company_id, status='ACTIVE'))

    # Load Minimum Wages
    min_wages = list(MinimumWage.objects.filter(company_id=company_id))

    # Eligible Guards
    guards = Employee.objects.filter(
        company_id=company_id,
        date_joined__lte=run.period_end
    ).exclude(employment_status='terminated', exit_date__lt=run.period_start)

    calculated_results = []
    overall_hash_builder = []

    for guard in guards:
        # Effective-Dated Salary Assignments (AC14.3, AC14.4, AC14.5)
        assignments = list(GuardSalaryAssignment.objects.filter(
            guard_id=guard.employee_id,
            status='ACTIVE',
            effective_from__lte=run.period_end
        ).filter(models_condition_assignment(run.period_start)).order_by('effective_from'))

        if not assignments:
            continue

        # Attendance query
        att_records = list(AttendanceRecord.objects.filter(
            employee=guard,
            duty_date__gte=run.period_start,
            duty_date__lte=run.period_end
        ))

        # Payable days calculation
        if att_records:
            payable_days = Decimal('0.00')
            reg_mins = 0
            ot_mins = 0
            for ar in att_records:
                if ar.status in ['present', 'approved']:
                    payable_days += Decimal('1.00')
                elif ar.status == 'half_day':
                    payable_days += Decimal('0.50')
                elif ar.status in ['paid_leave', 'leave_approved']:
                    payable_days += Decimal('1.00')
                elif ar.status == 'weekly_off':
                    payable_days += Decimal('1.00')
                
                reg_mins += (ar.regular_minutes or 0)
                # Overtime verification with Module 5 / status (AC14.11)
                if ar.overtime_minutes and ar.overtime_minutes > 0:
                    if ar.status == 'approved' or getattr(ar, 'is_manual', False) or ar.assignment_id:
                        ot_mins += ar.overtime_minutes
        else:
            # Standard month calculation when no specific punch records exist
            payable_days = month_length
            reg_mins = int(month_length * 8 * 60)
            ot_mins = 0

        # Handle Mid-Month Salary Split (AC14.5, Section 8.5)
        # If there are multiple assignments, calculate each segment
        gross_earnings = Decimal('0.00')
        lines_to_create = []
        basic_monthly_rate = Decimal('0.00')

        if len(assignments) == 1:
            primary_assignment = assignments[0]
            struct_lines = SalaryStructureLine.objects.filter(structure=primary_assignment.structure).select_related('component')
            for sline in struct_lines:
                comp = sline.component
                if comp.component_type == 'EARNING':
                    if sline.calculation_type == 'FIXED':
                        base_amt = sline.amount
                    else:
                        base_amt = sline.amount

                    if comp.component_code == 'BASIC':
                        basic_monthly_rate = base_amt

                    if comp.proration_enabled:
                        prorated = round((base_amt * payable_days) / month_length, 2)
                    else:
                        prorated = base_amt

                    gross_earnings += prorated
                    lines_to_create.append({
                        "component_id": comp.component_id,
                        "line_type": "EARNING",
                        "code": comp.component_code,
                        "description": comp.component_name,
                        "amount": prorated,
                        "formula_reference": f"{base_amt} * {payable_days} / {month_length}" if comp.proration_enabled else f"Fixed {base_amt}"
                    })
        else:
            # Split period across assignments
            primary_assignment = assignments[-1]
            seg_days_total = 0
            for idx, asgn in enumerate(assignments):
                seg_start = max(run.period_start, asgn.effective_from)
                seg_end = min(run.period_end, asgn.effective_to) if asgn.effective_to else run.period_end
                seg_days = (seg_end - seg_start).days + 1
                seg_days_total += seg_days

                struct_lines = SalaryStructureLine.objects.filter(structure=asgn.structure).select_related('component')
                for sline in struct_lines:
                    comp = sline.component
                    if comp.component_type == 'EARNING':
                        if comp.component_code == 'BASIC':
                            basic_monthly_rate = sline.amount
                        prorated_seg = round((sline.amount * Decimal(seg_days)) / month_length, 2)
                        gross_earnings += prorated_seg
                        lines_to_create.append({
                            "component_id": comp.component_id,
                            "line_type": "EARNING",
                            "code": f"{comp.component_code} (Split {seg_start.strftime('%d/%m')}-{seg_end.strftime('%d/%m')})",
                            "description": f"{comp.component_name} - Segment",
                            "amount": prorated_seg,
                            "formula_reference": f"{sline.amount} * {seg_days} / {month_length}"
                        })

        # Overtime Calculation (AC14.12, Section 8.9)
        if ot_mins > 0 and basic_monthly_rate > 0:
            ot_hours = Decimal(str(ot_mins)) / Decimal('60.00')
            hourly_rate = basic_monthly_rate / (month_length * Decimal('8.00'))
            ot_earnings = round(hourly_rate * Decimal('2.00') * ot_hours, 2)
            gross_earnings += ot_earnings
            lines_to_create.append({
                "component_id": None,
                "line_type": "EARNING",
                "code": "OVERTIME",
                "description": f"Approved Overtime ({ot_mins} mins @ 2x hourly rate)",
                "amount": ot_earnings,
                "formula_reference": f"({basic_monthly_rate} / ({month_length} * 8)) * 2 * {ot_hours:.2f} hrs"
            })

        # Statutory Deductions & Employer Contributions (AC14.13, AC14.18)
        employee_deductions = Decimal('0.00')
        employer_contributions = Decimal('0.00')

        for s_rule in stat_rules:
            # Calculate applicable wage base
            wage_base = Decimal('0.00')
            for l in lines_to_create:
                if l['line_type'] == 'EARNING':
                    # Check wage base components or scheme flag
                    if s_rule.wage_base_components and l['code'] in s_rule.wage_base_components:
                        wage_base += l['amount']
                    elif l['code'].startswith('BASIC') or l['code'].startswith('DA'):
                        wage_base += l['amount']

            if wage_base > 0:
                calc_base = wage_base
                if s_rule.wage_ceiling and calc_base > s_rule.wage_ceiling:
                    calc_base = s_rule.wage_ceiling

                if s_rule.employee_rate and s_rule.employee_rate > 0:
                    emp_amt = round(calc_base * s_rule.employee_rate, 2)
                    employee_deductions += emp_amt
                    lines_to_create.append({
                        "component_id": None,
                        "line_type": "STATUTORY_DEDUCTION",
                        "code": f"{s_rule.scheme}_EE",
                        "description": f"Employee {s_rule.scheme} Contribution ({float(s_rule.employee_rate)*100:.1f}%)",
                        "amount": emp_amt,
                        "rule_version": f"v{s_rule.version}",
                        "formula_reference": f"{calc_base} * {s_rule.employee_rate}"
                    })

                if s_rule.employer_rate and s_rule.employer_rate > 0:
                    empr_amt = round(calc_base * s_rule.employer_rate, 2)
                    employer_contributions += empr_amt
                    lines_to_create.append({
                        "component_id": None,
                        "line_type": "EMPLOYER_CONTRIBUTION",
                        "code": f"{s_rule.scheme}_ER",
                        "description": f"Employer {s_rule.scheme} Contribution ({float(s_rule.employer_rate)*100:.1f}%) [Separate]",
                        "amount": empr_amt,
                        "rule_version": f"v{s_rule.version}",
                        "formula_reference": f"{calc_base} * {s_rule.employer_rate}"
                    })

                # PT Slabs Check
                if s_rule.scheme == 'PROFESSIONAL_TAX' and s_rule.slabs:
                    for slab in s_rule.slabs:
                        s_min = Decimal(str(slab.get('min', 0)))
                        s_max = Decimal(str(slab.get('max', 9999999)))
                        if s_min <= wage_base <= s_max:
                            pt_val = Decimal(str(slab.get('amount', 0)))
                            if pt_val > 0:
                                employee_deductions += pt_val
                                lines_to_create.append({
                                    "component_id": None,
                                    "line_type": "STATUTORY_DEDUCTION",
                                    "code": "PROF_TAX",
                                    "description": f"Professional Tax (Slab {s_min}-{s_max})",
                                    "amount": pt_val,
                                    "rule_version": f"v{s_rule.version}",
                                    "formula_reference": f"Slab rate for wage {wage_base}"
                                })
                            break

        # Approved Manual Deductions (AC14.23, AC14.24, AC14.25)
        manual_deds = ManualDeduction.objects.filter(
            guard_id=guard.employee_id,
            status='APPROVED',
            applied_in_run_id__isnull=True
        )
        for md in manual_deds:
            employee_deductions += md.amount
            lines_to_create.append({
                "component_id": None,
                "line_type": "MANUAL_DEDUCTION",
                "code": f"DED_{md.category}",
                "description": f"Approved Manual Deduction - {md.category}: {md.reason}",
                "amount": md.amount,
                "source_reference": str(md.deduction_id),
                "formula_reference": f"Approved entry by admin"
            })

        # Advance & Loan Recovery with Net Pay Zero-Floor (AC14.27, AC14.28, AC14.37)
        advances = Advance.objects.filter(
            guard_id=guard.employee_id,
            status__in=['APPROVED', 'ISSUED', 'RECOVERING']
        )
        for adv in advances:
            # compute current balance
            ledger = adv.ledger_entries.all()
            issued = sum(e.amount for e in ledger if e.entry_type == 'ISSUE')
            recovered = sum(e.amount for e in ledger if e.entry_type in ('RECOVERY', 'WRITE_OFF'))
            adjusted = sum(e.amount for e in ledger if e.entry_type == 'ADJUSTMENT')
            balance = max(Decimal('0.00'), issued - recovered + adjusted)

            if balance > 0:
                planned_rec = min(adv.recovery_value, adv.max_per_instalment, balance)
                # Available net earnings before advance
                current_net = gross_earnings - employee_deductions
                if current_net <= Decimal('0.00'):
                    actual_rec = Decimal('0.00')  # Zero floor prevents negative net pay!
                else:
                    actual_rec = min(planned_rec, current_net)

                if actual_rec > 0:
                    employee_deductions += actual_rec
                    lines_to_create.append({
                        "component_id": None,
                        "line_type": "ADVANCE_RECOVERY",
                        "code": "ADVANCE_RECOVERY",
                        "description": f"Advance Recovery ({actual_rec} of {balance} balance)",
                        "amount": actual_rec,
                        "source_reference": str(adv.advance_id),
                        "formula_reference": f"Min(Planned {planned_rec}, Available Net {current_net})"
                    })

        # Final Net Pay (AC14.37, Section 8.12)
        net_pay = max(Decimal('0.00'), gross_earnings - employee_deductions)

        # Minimum wage compliance check (AC14.7)
        is_held = False
        hold_reason = None
        for mw in min_wages:
            daily_equiv = gross_earnings / payable_days if payable_days > 0 else Decimal('0.00')
            if mw.pay_basis == 'DAILY' and daily_equiv < mw.amount:
                is_held = True
                hold_reason = f"Calculated daily rate ₹{daily_equiv:.2f} is below configured minimum wage ₹{mw.amount:.2f} for {mw.skill_category}."
                break

        # Result hash
        res_content = f"{guard.employee_id}:{gross_earnings}:{employee_deductions}:{net_pay}"
        res_hash = hashlib.sha256(res_content.encode('utf-8')).hexdigest()
        overall_hash_builder.append(res_hash)

        # Create Result
        result = PayrollResult.objects.create(
            run=run,
            guard_id=guard.employee_id,
            salary_assignment_id=primary_assignment.assignment_id,
            paid_days=payable_days,
            regular_minutes=reg_mins,
            overtime_minutes=ot_mins,
            gross_earnings=gross_earnings,
            employee_deductions=employee_deductions,
            employer_contributions=employer_contributions,
            net_pay=net_pay,
            is_held=is_held,
            hold_reason=hold_reason,
            calculation_details={
                "payable_days": float(payable_days),
                "month_length": float(month_length),
                "regular_minutes": reg_mins,
                "overtime_minutes": ot_mins,
                "guard_name": f"{guard.first_name} {guard.last_name or ''}".strip(),
                "employee_code": guard.employee_code,
                "assignments_used": [str(a.assignment_id) for a in assignments],
                "holding_exception": hold_reason
            },
            rule_versions={"paid_day_rule": str(paid_day_rule.rule_set_id) if paid_day_rule else "default"},
            result_hash=res_hash
        )

        for l in lines_to_create:
            PayrollResultLine.objects.create(
                result=result,
                component_id=l.get('component_id'),
                line_type=l['line_type'],
                code=l['code'],
                description=l['description'],
                amount=l['amount'],
                source_reference=l.get('source_reference'),
                formula_reference=l.get('formula_reference'),
                rule_version=l.get('rule_version')
            )

        calculated_results.append(result)

    # Compute Run Hash & Update Status
    combined_hash = hashlib.sha256(":".join(overall_hash_builder).encode('utf-8')).hexdigest()
    run.status = 'CALCULATED'
    run.prepared_by = preparer_id
    run.result_hash = combined_hash
    run.save()

    return {
        "run_id": str(run.run_id),
        "period_reference": run.period_reference,
        "run_type": run.run_type,
        "status": run.status,
        "guards_calculated": len(calculated_results),
        "total_gross": float(sum(r.gross_earnings for r in calculated_results)),
        "total_deductions": float(sum(r.employee_deductions for r in calculated_results)),
        "total_net": float(sum(r.net_pay for r in calculated_results)),
        "total_employer_contributions": float(sum(r.employer_contributions for r in calculated_results)),
        "held_count": sum(1 for r in calculated_results if r.is_held),
        "result_hash": combined_hash
    }


def approve_payroll_run(run_id, company_id, approver_id, force_override_reasons=None):
    """
    Approves and freezes a payroll run (PRD 6.7, AC14.10, AC14.29, AC14.30).
    Enforces segregation of duties: preparer cannot approve their own run.
    Blocks provisional runs.
    """
    try:
        run = PayrollRun.objects.get(run_id=run_id, company_id=company_id)
    except PayrollRun.DoesNotExist:
        raise NotFound("Payroll run not found.")

    if run.status not in ['CALCULATED', 'UNDER_REVIEW']:
        raise ValidationError(f"Run cannot be approved from status '{run.status}'. Must be CALCULATED or UNDER_REVIEW.")

    # AC14.10: Provisional run cannot be approved
    if run.run_type == 'PROVISIONAL':
        raise ValidationError("Provisional payroll run cannot be approved. Attendance period must be locked first (AC14.10).")

    # AC14.29: Segregation of Duties - Preparer cannot approve own run
    if run.prepared_by and str(run.prepared_by) == str(approver_id):
        raise PermissionDenied("Segregation of duties violation: The preparer of a payroll run cannot approve their own run (AC14.29).")

    # AC14.7, AC14.8: Minimum wage exceptions check
    unresolved_held = PayrollResult.objects.filter(run=run, is_held=True)
    if unresolved_held.exists() and not force_override_reasons:
        raise ValidationError(f"{unresolved_held.count()} guards have unresolved minimum wage exceptions. Admin override with documented reason is required (AC14.7, AC14.8).")

    with transaction.atomic():
        run.status = 'APPROVED'
        run.approved_by = approver_id
        run.approved_at = timezone.now()
        if force_override_reasons:
            run.notes = f"Approved with minimum wage override: {force_override_reasons}"
        run.save()

    return {
        "run_id": str(run.run_id),
        "status": run.status,
        "approved_by": str(run.approved_by),
        "approved_at": run.approved_at.isoformat(),
        "result_hash": run.result_hash
    }


def release_payroll_run(run_id, company_id, user_id):
    """
    Releases an approved payroll run for payment (PRD 6.8, AC14.38, AC14.39).
    Generates immutable payslips with PDF reference & hash, and commits advance recoveries.
    """
    try:
        run = PayrollRun.objects.get(run_id=run_id, company_id=company_id)
    except PayrollRun.DoesNotExist:
        raise NotFound("Payroll run not found.")

    if run.status != 'APPROVED':
        raise ValidationError(f"Only APPROVED payroll runs can be released for payment. Current status: '{run.status}'.")

    with transaction.atomic():
        run.status = 'RELEASED'
        run.save()

        results = PayrollResult.objects.filter(run=run).select_related('run')
        payslip_counter = 1

        for res in results:
            payslip_number = f"PS-{run.period_reference.replace('-', '')}-{str(payslip_counter).zfill(4)}"
            payslip_counter += 1

            # PDF hash generation
            slip_payload = f"{payslip_number}:{res.guard_id}:{res.net_pay}:{res.result_hash}"
            slip_hash = hashlib.sha256(slip_payload.encode('utf-8')).hexdigest()

            Payslip.objects.create(
                payslip_number=payslip_number,
                guard_id=res.guard_id,
                run=run,
                result=res,
                version=1,
                pdf_reference=f"/storage/payslips/{run.period_reference}/{payslip_number}.pdf",
                pdf_hash=slip_hash,
                is_latest=True
            )

            # Apply advance recoveries to ledger
            adv_lines = PayrollResultLine.objects.filter(result=res, line_type='ADVANCE_RECOVERY')
            for al in adv_lines:
                if al.source_reference:
                    try:
                        adv = Advance.objects.get(advance_id=al.source_reference)
                        AdvanceLedgerEntry.objects.create(
                            advance=adv,
                            entry_type='RECOVERY',
                            amount=al.amount,
                            entry_date=run.period_end,
                            payroll_run_id=run.run_id,
                            reason=f"Payroll recovery {run.period_reference}",
                            created_by=user_id,
                            approved_by=user_id
                        )
                        # Check remaining balance
                        ledger = adv.ledger_entries.all()
                        iss = sum(e.amount for e in ledger if e.entry_type == 'ISSUE')
                        rec = sum(e.amount for e in ledger if e.entry_type in ('RECOVERY', 'WRITE_OFF'))
                        adj = sum(e.amount for e in ledger if e.entry_type == 'ADJUSTMENT')
                        bal = max(Decimal('0.00'), iss - rec + adj)
                        if bal <= Decimal('0.00'):
                            adv.status = 'RECOVERED'
                        else:
                            adv.status = 'RECOVERING'
                        adv.save()
                    except Advance.DoesNotExist:
                        pass

            # Mark manual deductions as APPLIED
            man_lines = PayrollResultLine.objects.filter(result=res, line_type='MANUAL_DEDUCTION')
            for ml in man_lines:
                if ml.source_reference:
                    ManualDeduction.objects.filter(deduction_id=ml.source_reference).update(
                        status='APPLIED',
                        applied_in_run_id=run.run_id
                    )

    return {
        "run_id": str(run.run_id),
        "status": run.status,
        "payslips_generated": results.count()
    }


def record_payment(run_id, result_id, guard_id, amount, mode, bank_reference, recorder_id, witness=None):
    """
    Records an external payment disbursement with overpayment and duplicate checks (PRD 6.9, AC14.48, AC14.49).
    Enforces segregation: Run Approver cannot record payments (AC14.48).
    """
    amount = Decimal(str(amount))
    if amount <= Decimal('0.00'):
        raise ValidationError("Payment amount must be greater than zero.")

    try:
        run = PayrollRun.objects.get(run_id=run_id)
        result = PayrollResult.objects.get(result_id=result_id, run=run)
    except (PayrollRun.DoesNotExist, PayrollResult.DoesNotExist):
        raise NotFound("Payroll run or guard calculation result not found.")

    if run.status not in ['RELEASED', 'PARTIALLY_PAID', 'PAID']:
        raise ValidationError(f"Payments can only be recorded against RELEASED runs. Current status: '{run.status}'.")

    # AC14.48: Approver cannot record payment for the same run
    if run.approved_by and str(run.approved_by) == str(recorder_id):
        raise PermissionDenied("Segregation of duties violation: The approver of a payroll run cannot record payments for that run (AC14.48).")

    # Duplicate payment check (AC14.49)
    if bank_reference:
        dup = PaymentRecord.objects.filter(
            guard_id=guard_id,
            run=run,
            bank_reference=bank_reference
        ).exclude(status='REVERSED').exists()
        if dup:
            raise ValidationError(f"Duplicate payment rejected: A payment with reference '{bank_reference}' already exists for this guard in this run (AC14.49).")

    # Cumulative payment validation (AC14.48)
    existing_payments = PaymentRecord.objects.filter(result=result).exclude(status='REVERSED')
    already_paid = sum(p.amount for p in existing_payments)

    if already_paid + amount > result.net_pay:
        raise ValidationError(f"Overpayment rejected: Cumulative paid ₹{already_paid + amount:.2f} exceeds approved net pay ₹{result.net_pay:.2f} (AC14.48).")

    with transaction.atomic():
        payment = PaymentRecord.objects.create(
            run=run,
            result=result,
            guard_id=guard_id,
            payment_date=timezone.now().date(),
            amount=amount,
            mode=mode,
            bank_reference=bank_reference,
            status='PAID',
            witness_or_acknowledgement=witness,
            recorded_by=recorder_id
        )

        # Update run status
        all_results = PayrollResult.objects.filter(run=run)
        total_net = sum(r.net_pay for r in all_results)
        total_settled = sum(p.amount for p in PaymentRecord.objects.filter(run=run, status='PAID'))

        if total_settled >= total_net:
            run.status = 'PAID'
        else:
            run.status = 'PARTIALLY_PAID'
        run.save()

    return {
        "payment_id": str(payment.payment_id),
        "status": payment.status,
        "amount": float(payment.amount),
        "run_status": run.status
    }


def reverse_payment(payment_id, company_id, user_id, reversal_reason):
    """
    Reverses an incorrect payment record with mandatory justification (PRD 6.9, AC14.51).
    """
    if not reversal_reason:
        raise ValidationError("Reversal reason is required to reverse a payment (AC14.51).")

    try:
        payment = PaymentRecord.objects.get(payment_id=payment_id)
    except PaymentRecord.DoesNotExist:
        raise NotFound("Payment record not found.")

    if payment.status == 'REVERSED':
        raise ValidationError("Payment is already reversed.")

    with transaction.atomic():
        payment.status = 'REVERSED'
        payment.reversal_reason = reversal_reason
        payment.save()

        # Update run status back to PARTIALLY_PAID
        run = payment.run
        if run.status == 'PAID':
            run.status = 'PARTIALLY_PAID'
            run.save()

    return {
        "payment_id": str(payment.payment_id),
        "status": payment.status,
        "reversal_reason": payment.reversal_reason,
        "run_status": run.status
    }


def generate_bank_payment_file(run_id, company_id):
    """
    Generates standard bank transfer file (CSV) for unpaid net amounts in an approved/released run (AC14.67).
    """
    try:
        run = PayrollRun.objects.get(run_id=run_id, company_id=company_id)
    except PayrollRun.DoesNotExist:
        raise NotFound("Payroll run not found.")

    results = PayrollResult.objects.filter(run=run).select_related('run')
    csv_rows = ["BeneficiaryName,AccountNumber,IFSC,Amount,Reference,PaymentDetails"]

    for r in results:
        # Check remaining payable
        paid = sum(p.amount for p in PaymentRecord.objects.filter(result=r, status='PAID'))
        unpaid = r.net_pay - paid
        if unpaid > Decimal('0.00'):
            try:
                guard = Employee.objects.get(employee_id=r.guard_id)
                b_info = guard.bank_details or {}
                acc = b_info.get('account_number', 'PENDING_ACC')
                ifsc = b_info.get('ifsc', 'PENDING_IFSC')
                name = f"{guard.first_name} {guard.last_name or ''}".strip()
            except Employee.DoesNotExist:
                name = "Unknown Guard"
                acc = "UNKNOWN"
                ifsc = "UNKNOWN"

            csv_rows.append(f'"{name}","{acc}","{ifsc}",{unpaid:.2f},"SALARY_{run.period_reference}","Salary for {run.period_reference}"')

    return "\n".join(csv_rows)


def get_payroll_dashboard_data(company_id):
    """
    Admin payroll overview metrics and outstanding action cards (PRD 10.1, Screen 1).
    """
    now = timezone.now().date()
    current_period = f"{now.year}-{str(now.month).zfill(2)}"

    total_guards = Employee.objects.filter(company_id=company_id, employment_status='active').count()
    recent_runs = list(PayrollRun.objects.filter(company_id=company_id).order_by('-created_at')[:5].values(
        'run_id', 'period_reference', 'status', 'run_type', 'created_at', 'approved_at'
    ))

    pending_approvals = PayrollRun.objects.filter(company_id=company_id, status__in=['CALCULATED', 'UNDER_REVIEW']).count()
    pending_payments = PayrollRun.objects.filter(company_id=company_id, status__in=['RELEASED', 'PARTIALLY_PAID']).count()
    
    # Advances outstanding
    advances = Advance.objects.filter(company_id=company_id, status__in=['APPROVED', 'ISSUED', 'RECOVERING'])
    total_adv_outstanding = Decimal('0.00')
    for a in advances:
        ledger = a.ledger_entries.all()
        iss = sum(e.amount for e in ledger if e.entry_type == 'ISSUE')
        rec = sum(e.amount for e in ledger if e.entry_type in ('RECOVERY', 'WRITE_OFF'))
        total_adv_outstanding += max(Decimal('0.00'), iss - rec)

    return {
        "current_period": current_period,
        "total_active_guards": total_guards,
        "pending_run_approvals": pending_approvals,
        "pending_payments_count": pending_payments,
        "total_advances_outstanding": float(total_adv_outstanding),
        "recent_runs": recent_runs
    }
