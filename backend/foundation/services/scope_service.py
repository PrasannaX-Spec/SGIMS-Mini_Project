import time
import logging
from datetime import date
from django.db.models import Q
from rest_framework import permissions
from rest_framework.exceptions import PermissionDenied, NotFound, AuthenticationFailed
from foundation.models import ScopeGrant, User
from foundation.resources import translate

logger = logging.getLogger(__name__)

# Capability matrix mapping capability code -> set of allowed roles
# (PRD Section 6 Matrix)
CAPABILITY_MAP = {
    # 1. Foundation
    'foundation.signin.web': {'ADMIN', 'SUPERVISOR'},
    'foundation.signin.mobile': {'SUPERVISOR', 'GUARD', 'CLIENT'},
    'foundation.user.create_edit': {'ADMIN'},
    'foundation.user.view': {'ADMIN'},
    'foundation.user.manage': {'ADMIN'},
    'foundation.device.decide': {'ADMIN'},
    'foundation.login_history.view': {'ADMIN'},
    'foundation.profile.self_manage': {'ADMIN', 'SUPERVISOR', 'GUARD', 'CLIENT'},
    'foundation.notification.read': {'ADMIN', 'SUPERVISOR', 'GUARD', 'CLIENT'},
    'foundation.audit.view': {'ADMIN'},
    'foundation.settings.manage': {'ADMIN'},
    'foundation.legal.read': {'ADMIN', 'SUPERVISOR', 'GUARD', 'CLIENT'},

    # 2. Master data
    'master_data.manage': {'ADMIN'},
    'master_data.view_sites': {'ADMIN', 'SUPERVISOR', 'GUARD', 'CLIENT'},
    'master_data.view_client': {'ADMIN', 'SUPERVISOR', 'CLIENT'},

    # 3. Guard management
    'guard.manage': {'ADMIN'},
    'guard.view_profile': {'ADMIN', 'SUPERVISOR', 'GUARD'},

    # 4. Service request & quotation
    'service_request.raise': {'ADMIN', 'CLIENT'},
    'service_request.view': {'ADMIN', 'CLIENT'},
    'quotation.manage': {'ADMIN'},
    'quotation.decide': {'CLIENT'},

    # 5. Deployment & roster
    'roster.manage': {'ADMIN'},
    'roster.view': {'ADMIN', 'SUPERVISOR', 'GUARD', 'CLIENT'},

    # 6. Attendance
    'attendance.check_in_out': {'GUARD'},
    'attendance.capture': {'ADMIN', 'SUPERVISOR', 'GUARD'},
    'attendance.view': {'ADMIN', 'SUPERVISOR', 'GUARD', 'CLIENT'},
    'attendance.read': {'ADMIN', 'SUPERVISOR', 'GUARD', 'CLIENT'},
    'attendance.client_read': {'CLIENT'},
    'attendance.approve': {'ADMIN', 'SUPERVISOR'},
    'attendance.edit': {'ADMIN', 'SUPERVISOR'},
    'attendance.correct': {'ADMIN', 'SUPERVISOR'},
    'attendance.lock': {'ADMIN'},
    'attendance.export': {'ADMIN', 'SUPERVISOR'},

    # 7. Live monitoring
    'monitoring.view_live': {'ADMIN', 'SUPERVISOR'},
    'monitoring.ingest': {'ADMIN', 'SUPERVISOR', 'GUARD'},
    'monitoring.manage_alerts': {'ADMIN', 'SUPERVISOR'},
    'monitoring.ping_respond': {'GUARD'},
    'monitoring.config': {'ADMIN'},
    'monitoring.historical_trail': {'ADMIN', 'SUPERVISOR'},
    'monitoring.client_safe': {'ADMIN', 'CLIENT'},

    # 8. Incidents & requests
    'incident.raise': {'ADMIN', 'SUPERVISOR', 'GUARD'},
    'incident.view': {'ADMIN', 'SUPERVISOR', 'GUARD', 'CLIENT'},
    'incident.manage': {'ADMIN', 'SUPERVISOR'},
    'guard_request.raise': {'GUARD'},
    'guard_request.decide': {'ADMIN', 'SUPERVISOR'},

    # 9. Panic & escalation
    'panic.press': {'GUARD'},
    'panic.manage': {'ADMIN', 'SUPERVISOR'},
    'panic.view': {'ADMIN', 'SUPERVISOR', 'GUARD'},
    'panic.configure_escalation': {'ADMIN'},

    # 10. Client portal
    'client_portal.view': {'CLIENT'},
    'client_portal.raise_ticket': {'CLIENT'},

    # 11. Billing
    'billing.manage': {'ADMIN'},
    'billing.view': {'ADMIN', 'CLIENT'},

    # 12. Armed & weapons
    'weapons.manage': {'ADMIN'},
    'weapons.issue_return': {'ADMIN', 'SUPERVISOR'},
    'weapons.view_own': {'GUARD'},

    # 13. Reports & dashboards
    'reports.view': {'ADMIN', 'SUPERVISOR', 'CLIENT'},
    'reports.export': {'ADMIN', 'SUPERVISOR'},
}

# Scope Grant cache (user_id -> {'grants': [...], 'ts': float})
_SCOPE_CACHE = {}
SCOPE_CACHE_TTL = 60  # 60 seconds (FR-1.37)


def invalidate_user_scope_cache(user_id):
    """
    Invalidates the cached scope grants for a user. (FR-1.37)
    """
    _SCOPE_CACHE.pop(str(user_id), None)


def get_active_scope_grants(user: User):
    """
    Fetches active scope grants for a user with up to 60s caching.
    Grants must be effective today (effective_from <= today <= effective_to).
    """
    if not user or not user.is_authenticated:
        return []

    user_id_str = str(user.user_id)
    cached = _SCOPE_CACHE.get(user_id_str)
    now = time.time()
    if cached and (now - cached['ts']) < SCOPE_CACHE_TTL:
        return cached['grants']

    today = date.today()
    grants = list(ScopeGrant.objects.filter(
        user=user,
        effective_from__lte=today
    ).filter(
        Q(effective_to__isnull=True) | Q(effective_to__gte=today)
    ).values('scope_type', 'target_id'))

    _SCOPE_CACHE[user_id_str] = {'grants': grants, 'ts': now}
    return grants


def check_permission(user: User, capability_code: str) -> bool:
    """
    Checks if a user's role has permission for the specified capability.
    Unknown capability code raises a programming error at startup / dev (FR-1.31 & Interface §10).
    """
    if capability_code not in CAPABILITY_MAP:
        raise KeyError(f"Unknown capability code: '{capability_code}'. Must be declared in CAPABILITY_MAP.")

    if not user or not getattr(user, 'is_authenticated', False):
        return False

    if getattr(user, 'status', None) != 'ACTIVE':
        return False

    allowed_roles = CAPABILITY_MAP[capability_code]
    return user.role in allowed_roles


def scope_filter(user: User, record_type: str) -> Q:
    """
    Returns a Django Q filter applying the user's role and scope grants to a database query.
    (FR-1.32 to FR-1.36, AC-27 to AC-30)
    """
    if not user or not user.is_authenticated or user.status != 'ACTIVE':
        return Q(pk__in=[])  # Deny all rows

    # Always restrict to company_id (D1)
    base_filter = Q(company_id=user.company_id)

    # 1. ADMIN has ALL scope
    if user.role == 'ADMIN':
        return base_filter

    # 2. CLIENT has COMPANY scope (linked client_company_id)
    if user.role == 'CLIENT':
        if not user.client_company_id:
            return Q(pk__in=[])
        if record_type in ('client', 'client_company'):
            return base_filter & Q(client_id=user.client_company_id)
        elif record_type in ('site', 'client_site'):
            return base_filter & Q(client_id=user.client_company_id)
        elif record_type in ('incident', 'ticket', 'attendance', 'invoice', 'roster'):
            return base_filter & Q(client_id=user.client_company_id)
        return base_filter & Q(client_id=user.client_company_id)

    # 3. GUARD has OWN_PROFILE scope (linked guard_profile_id)
    if user.role == 'GUARD':
        if not user.guard_profile_id:
            return Q(pk__in=[])
        if record_type in ('guard_profile', 'employee'):
            return base_filter & Q(employee_id=user.guard_profile_id)
        elif record_type in ('attendance', 'shift_assignment', 'patrol_round'):
            return base_filter & Q(employee_id=user.guard_profile_id)
        elif record_type == 'incident':
            return base_filter & Q(reported_by_employee_id=user.guard_profile_id)
        elif record_type == 'notification':
            return base_filter & Q(user_id=user.user_id)
        return base_filter & Q(user_id=user.user_id)

    # 4. SUPERVISOR has ASSIGNED scope (sites and guards in scope grants)
    if user.role == 'SUPERVISOR':
        grants = get_active_scope_grants(user)
        assigned_sites = [g['target_id'] for g in grants if g['scope_type'] == 'SITE' and g['target_id']]
        assigned_guards = [g['target_id'] for g in grants if g['scope_type'] == 'GUARD' and g['target_id']]

        if not assigned_sites and not assigned_guards:
            return Q(pk__in=[])  # No grants -> sees nothing (Interface §10)

        if record_type in ('site', 'client_site'):
            return base_filter & Q(site_id__in=assigned_sites)
        elif record_type in ('guard_profile', 'employee'):
            return base_filter & (Q(employee_id__in=assigned_guards) | Q(site_id__in=assigned_sites))
        elif record_type in ('attendance', 'shift_assignment'):
            site_q = Q(site_id__in=assigned_sites) if assigned_sites else Q()
            guard_q = Q(employee_id__in=assigned_guards) if assigned_guards else Q()
            return base_filter & (site_q | guard_q)
        elif record_type == 'incident':
            return base_filter & Q(site_id__in=assigned_sites)
        return base_filter & Q(site_id__in=assigned_sites)

    return Q(pk__in=[])


def is_in_scope(user: User, record_type: str, record_id) -> bool:
    """
    Checks if a specific record is within the user's scope.
    (FR-1.36, AC-28, AC-29, AC-30)
    """
    if not user or not user.is_authenticated or user.status != 'ACTIVE':
        return False

    if user.role == 'ADMIN':
        return True

    # For user records (e.g. self-profile)
    if record_type == 'user':
        if str(record_id) == str(user.user_id):
            return True
        return False

    # Check via scope grants
    if user.role == 'SUPERVISOR':
        grants = get_active_scope_grants(user)
        target_ids = {str(g['target_id']) for g in grants if g['target_id']}
        return str(record_id) in target_ids

    if user.role == 'CLIENT':
        return str(record_id) == str(user.client_company_id)

    if user.role == 'GUARD':
        return str(record_id) == str(user.guard_profile_id)

    return False


class HasCapabilityAndScope(permissions.BasePermission):
    """
    Central DRF permission class that enforces:
    1. Capability check first (FR-1.31) -> 403 if missing
    2. Scope check (FR-1.36) -> 404 if record out of scope
    """
    def has_permission(self, request, view):
        required_capability = getattr(view, 'required_capability', None)
        if not required_capability:
            # Route scan enforcement (FR-1.38)
            raise NotImplementedError(f"View {view.__class__.__name__} must declare 'required_capability'.")

        user = request.user
        if not user or not getattr(user, 'is_authenticated', False):
            raise AuthenticationFailed(translate('auth.session_revoked'))

        if getattr(user, 'status', None) != 'ACTIVE':
            raise AuthenticationFailed(translate('auth.account_inactive'))

        if not check_permission(user, required_capability):
            raise PermissionDenied(detail=translate('scope.access_denied'))
        return True

    def has_object_permission(self, request, view, obj):
        user = request.user
        record_type = getattr(view, 'record_type', None)
        record_id = getattr(obj, 'pk', None)

        if record_type and record_id:
            if not is_in_scope(user, record_type, record_id):
                # Returns 404 for out-of-scope records (FR-1.36, AC-28, AC-29, AC-30)
                raise NotFound(detail=translate('scope.record_not_found'))
        return True


class ScopedQuerySetMixin:
    """
    DRF Viewset mixin that applies scope filtering directly inside the DB query.
    (FR-1.36, AC-27)
    """
    record_type = None

    def get_queryset(self):
        qs = super().get_queryset()
        if not self.record_type:
            raise NotImplementedError(f"Viewset {self.__class__.__name__} must define 'record_type'.")
        filter_q = scope_filter(self.request.user, self.record_type)
        return qs.filter(filter_q)
