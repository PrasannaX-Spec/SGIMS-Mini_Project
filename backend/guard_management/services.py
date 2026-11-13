import hashlib
import json
import secrets
from datetime import datetime, date, timedelta
from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import ValidationError, PermissionDenied, NotFound

from guard_management.models import (
    Employee, EmployeeDocument, EmployeeTraining, EmployeeCheck,
    LeaveRequest, GuardStatusHistory, GuardDisciplinaryRecord,
    GuardIdCard, ProfileChangeRequest
)
from master_data.models import Company, PostType
from foundation.models import User
from foundation.services.audit_service import write_audit_event
from foundation.services.settings_service import get_setting


# ==============================================================================
# LIFECYCLE STATE TRANSITIONS (FR-3.5)
# ==============================================================================
ALLOWED_TRANSITIONS = {
    'applicant': {'under_verification'},
    'under_verification': {'approved', 'applicant'},
    'approved': {'active', 'suspended'},
    'active': {'on_leave', 'suspended', 'resigned', 'terminated'},
    'on_leave': {'active', 'suspended', 'resigned', 'terminated'},
    'suspended': {'active', 'resigned', 'terminated'},
    'resigned': set(),   # Terminal
    'terminated': set(), # Terminal
}


def hash_identifier(identifier: str) -> str:
    """Computes a SHA-256 one-way hash for duplicate detection without exposing raw ID."""
    if not identifier:
        return None
    return hashlib.sha256(identifier.strip().encode('utf-8')).hexdigest()


def generate_employee_code(company_id):
    """Auto-generates sequential employee code e.g. SEC-GRD-000101 (FR-3.29, AC-04, AC-05)."""
    prefix = get_setting('employee_code_prefix', company_id) or 'SEC-GRD'
    count = Employee.objects.filter(company_id=company_id).count() + 101
    code = f"{prefix}-{count:06d}"
    while Employee.objects.filter(company_id=company_id, employee_code=code).exists():
        count += 1
        code = f"{prefix}-{count:06d}"
    return code


# ==============================================================================
# 1. GUARD REGISTRATION & PROFILE (FR-3.18 to FR-3.42, AC-01 to AC-05)
# ==============================================================================

def register_guard(company_id, data, actor_user, request=None):
    phone = data.get('phone', '').strip()
    if not phone:
        raise ValidationError({'phone': 'Primary phone number is required.'})

    if Employee.objects.filter(phone=phone).exists():
        raise ValidationError({'phone': f"A guard with phone number '{phone}' already exists (AC-02)."})

    dob_val = data.get('date_of_birth')
    if not dob_val:
        raise ValidationError({'date_of_birth': 'Date of birth is required.'})

    if isinstance(dob_val, str):
        dob = datetime.strptime(dob_val, '%Y-%m-%d').date()
    else:
        dob = dob_val

    # Minimum age check (AC-03, FR-3.21)
    min_age = int(get_setting('guard_min_age_years', company_id) or 18)
    today = date.today()
    age = today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))
    if age < min_age:
        raise ValidationError({'date_of_birth': f"Guard must be at least {min_age} years old (calculated age: {age})."})

    aadhaar_num = data.get('aadhaar_number', '').strip()
    aadhaar_hash = None
    aadhaar_masked = None
    if aadhaar_num:
        aadhaar_hash = hash_identifier(aadhaar_num)
        if Employee.objects.filter(company_id=company_id, aadhaar_hash=aadhaar_hash).exists():
            raise ValidationError({'aadhaar_number': 'Duplicate identity record detected (FR-3.34).'})
        aadhaar_masked = f"XXXX-XXXX-{aadhaar_num[-4:]}" if len(aadhaar_num) >= 4 else "XXXX"

    emp_code = generate_employee_code(company_id)

    full_name = data.get('full_name', '').strip()
    name_parts = full_name.split()
    first_name = name_parts[0] if name_parts else 'Guard'
    last_name = " ".join(name_parts[1:]) if len(name_parts) > 1 else ''

    joining_date = data.get('date_joined') or today
    if isinstance(joining_date, str):
        joining_date = datetime.strptime(joining_date, '%Y-%m-%d').date()

    emp = Employee.objects.create(
        company_id=company_id,
        employee_code=emp_code,
        first_name=first_name,
        last_name=last_name,
        father_guardian_name=data.get('father_guardian_name'),
        date_of_birth=dob,
        gender=data.get('gender', 'male'),
        phone=phone,
        email=data.get('email'),
        address={'permanent': data.get('permanent_address'), 'current': data.get('current_address')},
        emergency_contact=data.get('emergency_contact'),
        date_joined=joining_date,
        lifecycle_status='applicant',
        blood_group=data.get('blood_group'),
        marital_status=data.get('marital_status'),
        height_cm=data.get('height_cm'),
        weight_kg=data.get('weight_kg'),
        qualification=data.get('qualification'),
        experience_summary=data.get('experience_summary'),
        is_ex_serviceman=data.get('is_ex_serviceman', False),
        reference_photo_url=data.get('reference_photo_url'),
        aadhaar_masked=aadhaar_masked,
        aadhaar_hash=aadhaar_hash,
        home_district=data.get('home_district'),
        preferred_work_area=data.get('preferred_work_area'),
        post_type_id=data.get('post_type_id'),
    )

    # Initial status history record
    GuardStatusHistory.objects.create(
        employee=emp,
        previous_status=None,
        new_status='applicant',
        reason='Initial walk-in guard registration',
        changed_by_user_id=actor_user.user_id
    )

    write_audit_event(
        action_code='guard.register',
        actor_user=actor_user,
        module='guard_management',
        record_type='EMPLOYEE',
        record_id=str(emp.employee_id),
        new_values={'employee_code': emp.employee_code, 'status': emp.lifecycle_status},
        reason=f"Registered guard {emp.employee_code} ({emp.full_name})",
        request=request
    )
    return emp


# ==============================================================================
# 2. LIFECYCLE TRANSITIONS (FR-3.1 to FR-3.17, AC-06 to AC-10)
# ==============================================================================

def change_guard_status(employee_id, new_status, reason, actor_user, request=None):
    emp = Employee.objects.get(employee_id=employee_id)
    old_status = emp.lifecycle_status

    if not reason or not reason.strip():
        raise ValidationError({'reason': 'A reason is mandatory for any lifecycle status change (AC-08).'})

    allowed_next = ALLOWED_TRANSITIONS.get(old_status, set())
    if new_status not in allowed_next:
        raise ValidationError({
            'status': f"Invalid status transition from '{old_status}' to '{new_status}' (FR-3.5, AC-07)."
        })

    # Approval stage check: Emergency contact mandatory before approval (FR-3.24)
    if new_status == 'approved':
        if not emp.emergency_contact or not emp.emergency_contact.get('phone'):
            raise ValidationError({
                'emergency_contact': 'Emergency contact information is mandatory before approval (FR-3.24, E-03).'
            })

    with transaction.atomic():
        emp.lifecycle_status = new_status
        if new_status in ('resigned', 'terminated'):
            emp.exit_date = date.today()
            emp.employment_status = new_status
        elif new_status == 'active':
            emp.employment_status = 'active'
        elif new_status == 'on_leave':
            emp.employment_status = 'on_leave'
        elif new_status == 'suspended':
            emp.employment_status = 'suspended'

        emp.save()

        # Record Status History
        GuardStatusHistory.objects.create(
            employee=emp,
            previous_status=old_status,
            new_status=new_status,
            reason=reason.strip(),
            changed_by_user_id=actor_user.user_id
        )

        # Synchronize with Module 1 User account if linked (AC-10, FR-3.104, FR-3.105)
        linked_user = User.objects.filter(guard_profile_id=emp.employee_id).first()
        if linked_user:
            if new_status in ('resigned', 'terminated'):
                linked_user.status = 'INACTIVE'
                linked_user.account_status = 'disabled'
                linked_user.deactivated_at = timezone.now()
                linked_user.deactivated_by = actor_user.user_id
                linked_user.deactivation_reason = f"Guard employment {new_status}: {reason}"
                linked_user.save()
            elif new_status == 'suspended':
                linked_user.account_status = 'locked'
                linked_user.save()
            elif new_status == 'active' and old_status == 'suspended':
                linked_user.account_status = 'active'
                linked_user.save()

    write_audit_event(
        action_code='guard.status_changed',
        actor_user=actor_user,
        module='guard_management',
        record_type='EMPLOYEE',
        record_id=str(emp.employee_id),
        old_values={'status': old_status},
        new_values={'status': new_status},
        reason=f"Changed guard status to {new_status}: {reason}",
        request=request
    )
    return emp


# ==============================================================================
# 3. DEPLOYABILITY DECISION ENGINE (FR-3.10 to FR-3.17, AC-11 to AC-17)
# ==============================================================================

def is_guard_deployable_on_date(employee_id, target_date=None, post_type_id=None):
    """
    Authoritative deployability evaluator (FR-3.10, AC-11 to AC-17).
    A guard is deployable only when all conditions are satisfied:
      1. Guard status is Active.
      2. All configured mandatory documents are present, Verified, and not expired.
      3. Police verification cleared & valid.
      4. Medical fitness cleared & valid.
      5. Mandatory training completed and valid.
      6. No approved unavailability on target_date.
      7. For armed posts: verified arms licence present and unexpired.
    """
    if target_date is None:
        target_date = date.today()
    elif isinstance(target_date, str):
        target_date = datetime.strptime(target_date, '%Y-%m-%d').date()

    emp = Employee.objects.get(employee_id=employee_id)
    failure_reasons = []

    # 1. Lifecycle status must be Active (AC-09)
    if emp.lifecycle_status != 'active':
        failure_reasons.append(f"Guard lifecycle status is '{emp.lifecycle_status}', not 'active'.")

    # 2. Mandatory Documents
    mandatory_docs_str = get_setting('mandatory_doc_types', emp.company_id) or 'identity_proof,address_proof'
    mandatory_docs = [d.strip() for d in mandatory_docs_str.split(',') if d.strip()]

    docs = EmployeeDocument.objects.filter(employee=emp, is_active=True)
    doc_type_map = {d.document_type: d for d in docs}

    for req_doc in mandatory_docs:
        if req_doc in ('police_verification', 'medical_fitness'):
            continue  # Handled in dedicated checks below
        doc = doc_type_map.get(req_doc)
        if not doc:
            failure_reasons.append(f"Missing mandatory document: '{req_doc}' (AC-12).")
        elif doc.verification_status != 'verified':
            failure_reasons.append(f"Mandatory document '{req_doc}' verification is '{doc.verification_status}' (AC-13).")
        elif doc.expiry_date and doc.expiry_date < target_date:
            failure_reasons.append(f"Mandatory document '{req_doc}' expired on {doc.expiry_date} (AC-14).")

    # 3. Police verification & Medical fitness (FR-3.51 to FR-3.53)
    if 'police_verification' in mandatory_docs:
        police_check = EmployeeCheck.objects.filter(
            employee=emp, check_type='police', status='cleared'
        ).filter(
            models_q_valid_until(target_date)
        ).first()
        if not police_check:
            failure_reasons.append("Police verification is pending or expired.")

    if 'medical_fitness' in mandatory_docs:
        med_check = EmployeeCheck.objects.filter(
            employee=emp, check_type='medical', status='cleared'
        ).filter(
            models_q_valid_until(target_date)
        ).first()
        if not med_check:
            failure_reasons.append("Medical fitness check is pending or expired.")

    # 4. Mandatory Training (AC-15, FR-3.69)
    mandatory_trainings_str = get_setting('mandatory_training_types', emp.company_id) or 'induction'
    mandatory_trainings = [t.strip() for t in mandatory_trainings_str.split(',') if t.strip()]

    for req_t in mandatory_trainings:
        passed_training = EmployeeTraining.objects.filter(
            employee=emp,
            result='passed',
            attendance_status='present'
        ).filter(
            models_q_valid_until(target_date)
        ).first()
        if not passed_training:
            failure_reasons.append(f"Mandatory training '{req_t}' is incomplete or expired (AC-15).")

    # 5. Unavailability / Leave on target_date (AC-17, FR-3.86)
    leave = LeaveRequest.objects.filter(
        employee=emp,
        status='approved',
        start_date__lte=target_date,
        end_date__gte=target_date
    ).first()
    if leave:
        failure_reasons.append(f"Guard has approved unavailability on {target_date} ({leave.leave_type}).")

    # 6. Armed Eligibility for armed posts (AC-16, FR-3.73, FR-3.74)
    if post_type_id:
        pt = PostType.objects.filter(post_type_id=post_type_id).first()
        if pt and pt.requires_armed_authorization:
            arms_licence = EmployeeDocument.objects.filter(
                employee=emp,
                document_type='arms_licence',
                verification_status='verified',
                is_active=True
            ).filter(
                models_q_expiry_date(target_date)
            ).first()
            if not arms_licence:
                failure_reasons.append("Armed post requires a valid verified arms licence document (AC-16).")

    is_deployable = len(failure_reasons) == 0
    return {
        'employee_id': str(emp.employee_id),
        'employee_code': emp.employee_code,
        'deployable': is_deployable,
        'current_status': emp.lifecycle_status,
        'failure_reasons': failure_reasons,
        'target_date': str(target_date)
    }


def models_q_valid_until(target_date):
    from django.db.models import Q
    return Q(valid_until__isnull=True) | Q(valid_until__gte=target_date)


def models_q_expiry_date(target_date):
    from django.db.models import Q
    return Q(expiry_date__isnull=True) | Q(expiry_date__gte=target_date)


# ==============================================================================
# 4. DOCUMENTS & VERIFICATION (FR-3.43 to FR-3.65, AC-18 to AC-22)
# ==============================================================================

def upload_guard_document(employee_id, doc_type, storage_key, filename, data, actor_user, request=None):
    emp = Employee.objects.get(employee_id=employee_id)
    doc_num = data.get('document_number', '').strip()
    issue_date = data.get('issue_date')
    expiry_date = data.get('expiry_date')

    # Deactivate existing document of same type to maintain version history (AC-19, FR-3.49)
    prev_doc = EmployeeDocument.objects.filter(employee=emp, document_type=doc_type, is_active=True).order_by('-version').first()
    next_version = 1
    if prev_doc:
        next_version = prev_doc.version + 1
        prev_doc.is_active = False
        prev_doc.save()

    doc = EmployeeDocument.objects.create(
        employee=emp,
        document_type=doc_type,
        storage_key=storage_key,
        original_filename=filename,
        document_number=doc_num,
        masked_number=f"XXXX-{doc_num[-4:]}" if len(doc_num) >= 4 else doc_num,
        number_hash=hash_identifier(doc_num),
        issue_date=issue_date,
        expiry_date=expiry_date,
        verification_status='pending',
        version=next_version,
        is_active=True
    )

    write_audit_event(
        action_code='guard.document_uploaded',
        actor_user=actor_user,
        module='guard_management',
        record_type='EMPLOYEE_DOCUMENT',
        record_id=str(doc.document_id),
        new_values={'doc_type': doc_type, 'version': next_version},
        reason=f"Uploaded {doc_type} for {emp.employee_code} (v{next_version})",
        request=request
    )
    return doc


def verify_guard_document(document_id, decision, rejection_reason, actor_user, request=None):
    doc = EmployeeDocument.objects.get(document_id=document_id)
    if decision == 'reject':
        if not rejection_reason or not rejection_reason.strip():
            raise ValidationError({'rejection_reason': 'Rejection reason is mandatory (AC-18, FR-3.47).'})
        doc.verification_status = 'rejected'
        doc.rejection_reason = rejection_reason.strip()
    elif decision == 'verify':
        doc.verification_status = 'verified'
        doc.verified_by = actor_user.user_id
        doc.verified_at = timezone.now()
    else:
        raise ValidationError({'decision': "Decision must be 'verify' or 'reject'."})

    doc.save()

    write_audit_event(
        action_code='guard.document_decided',
        actor_user=actor_user,
        module='guard_management',
        record_type='EMPLOYEE_DOCUMENT',
        record_id=str(doc.document_id),
        new_values={'verification_status': doc.verification_status},
        reason=f"{decision.capitalize()}ed document {doc.document_type} for {doc.employee.employee_code}",
        request=request
    )
    return doc


# ==============================================================================
# 5. BANK DETAILS & AUDITED REVEAL (FR-3.76 to FR-3.85, AC-26 to AC-28)
# ==============================================================================

def update_guard_bank_details(employee_id, bank_dict, actor_user, request=None):
    emp = Employee.objects.get(employee_id=employee_id)
    emp.bank_details = bank_dict
    emp.save()

    write_audit_event(
        action_code='guard.bank_details.updated',
        actor_user=actor_user,
        module='guard_management',
        record_type='EMPLOYEE',
        record_id=str(emp.employee_id),
        new_values={'bank_name': bank_dict.get('bank_name')},
        reason=f"Updated bank details for {emp.employee_code}",
        request=request
    )
    return emp


def reveal_guard_bank_details(employee_id, actor_user, request=None):
    """
    Explicit audited action to reveal full sensitive bank details (FR-3.82, FR-3.83, AC-27).
    """
    if actor_user.role != 'ADMIN':
        raise PermissionDenied("Only Admin may reveal sensitive bank details (AC-26).")

    emp = Employee.objects.get(employee_id=employee_id)
    raw_bank = emp.bank_details or {}

    write_audit_event(
        action_code='guard.bank_details.revealed',
        actor_user=actor_user,
        module='guard_management',
        record_type='EMPLOYEE',
        record_id=str(emp.employee_id),
        reason=f"Admin {actor_user.full_name} revealed bank details for {emp.employee_code}",
        request=request
    )
    return raw_bank


# ==============================================================================
# 6. GUARD ACCOUNT LINKING (FR-3.95 to FR-3.106, AC-34, AC-35)
# ==============================================================================

def create_guard_login_account(employee_id, actor_user, request=None):
    emp = Employee.objects.get(employee_id=employee_id)

    if emp.lifecycle_status in ('applicant', 'under_verification'):
        raise ValidationError({'detail': 'Guard must reach Approved status before an account can be created (FR-3.98).'})

    # 1-to-1 association check (AC-34, FR-3.96, FR-3.97)
    if User.objects.filter(guard_profile_id=emp.employee_id).exists():
        raise ValidationError({'detail': 'This guard profile is already linked to a login account.'})

    if User.objects.filter(phone=emp.phone).exists():
        raise ValidationError({'phone': f"A user account with phone '{emp.phone}' already exists."})

    from django.contrib.auth.hashers import make_password
    temp_pass = f"Grd@{secrets.token_hex(4)}"

    user = User.objects.create(
        company_id=emp.company_id,
        role='GUARD',
        status='ACTIVE',
        account_status='active',
        full_name=emp.full_name,
        phone=emp.phone,
        password_hash=make_password(temp_pass),
        must_change_password=True,
        guard_profile_id=emp.employee_id
    )

    write_audit_event(
        action_code='guard.account_created',
        actor_user=actor_user,
        module='guard_management',
        record_type='USER',
        record_id=str(user.user_id),
        new_values={'phone': user.phone, 'employee_code': emp.employee_code},
        reason=f"Created mobile login account for guard {emp.employee_code}",
        request=request
    )
    return user, temp_pass


# ==============================================================================
# 7. UNAVAILABILITY MANAGEMENT (FR-3.86 to FR-3.94, AC-31 to AC-33)
# ==============================================================================

def request_unavailability(employee_id, leave_type, start_date, end_date, reason, actor_user, request=None):
    emp = Employee.objects.get(employee_id=employee_id)
    if isinstance(start_date, str):
        start_date = datetime.strptime(start_date, '%Y-%m-%d').date()
    if isinstance(end_date, str):
        end_date = datetime.strptime(end_date, '%Y-%m-%d').date()

    if end_date < start_date:
        raise ValidationError({'end_date': 'End date must be greater than or equal to start date.'})

    initial_status = 'approved' if actor_user.role == 'ADMIN' else 'pending'

    leave = LeaveRequest.objects.create(
        employee=emp,
        leave_type=leave_type,
        start_date=start_date,
        end_date=end_date,
        reason=reason,
        status=initial_status,
        reviewed_by=actor_user.user_id if initial_status == 'approved' else None,
        reviewed_at=timezone.now() if initial_status == 'approved' else None
    )

    write_audit_event(
        action_code='guard.unavailability_requested',
        actor_user=actor_user,
        module='guard_management',
        record_type='LEAVE_REQUEST',
        record_id=str(leave.leave_request_id),
        new_values={'status': leave.status, 'start': str(start_date), 'end': str(end_date)},
        reason=f"Unavailability requested for {emp.employee_code} ({leave_type})",
        request=request
    )
    return leave


def decide_unavailability(leave_request_id, decision, actor_user, request=None):
    leave = LeaveRequest.objects.get(leave_request_id=leave_request_id)
    if decision not in ('approved', 'rejected'):
        raise ValidationError({'decision': "Decision must be 'approved' or 'rejected'."})

    leave.status = decision
    leave.reviewed_by = actor_user.user_id
    leave.reviewed_at = timezone.now()
    leave.save()

    write_audit_event(
        action_code='guard.unavailability_decided',
        actor_user=actor_user,
        module='guard_management',
        record_type='LEAVE_REQUEST',
        record_id=str(leave.leave_request_id),
        new_values={'status': leave.status},
        reason=f"{decision.capitalize()} unavailability for {leave.employee.employee_code}",
        request=request
    )
    return leave

