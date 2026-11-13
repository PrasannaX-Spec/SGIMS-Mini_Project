import time
import logging
from django.core.cache import cache
from foundation.models import SystemSetting, Company
from foundation.resources import translate

logger = logging.getLogger(__name__)

# System Settings Definitions according to PRD FR-1.89
SETTING_DEFINITIONS = {
    'failed_attempts_lockout': {
        'default': 5,
        'type': int,
        'min': 3,
        'max': 10,
        'label': 'Failed attempts before lockout',
        'used_by': 'FR-1.12'
    },
    'lockout_duration_minutes': {
        'default': 15,
        'type': int,
        'min': 5,
        'max': 1440,
        'label': 'Lockout duration (minutes)',
        'used_by': 'FR-1.12'
    },
    'web_idle_timeout_minutes': {
        'default': 30,
        'type': int,
        'min': 5,
        'max': 120,
        'label': 'Web idle timeout (minutes)',
        'used_by': 'FR-1.17'
    },
    'web_absolute_session_hours': {
        'default': 12,
        'type': int,
        'min': 1,
        'max': 24,
        'label': 'Web absolute session (hours)',
        'used_by': 'FR-1.17'
    },
    'app_refresh_token_days': {
        'default': 30,
        'type': int,
        'min': 7,
        'max': 90,
        'label': 'App refresh token life (days)',
        'used_by': 'FR-1.16'
    },
    'password_reset_link_minutes': {
        'default': 30,
        'type': int,
        'min': 10,
        'max': 120,
        'label': 'Password reset link life (minutes)',
        'used_by': 'FR-1.8'
    },
    'temporary_password_days': {
        'default': 7,
        'type': int,
        'min': 1,
        'max': 14,
        'label': 'Temporary password life (days)',
        'used_by': 'FR-1.10'
    },
    'device_change_expiry_days': {
        'default': 7,
        'type': int,
        'min': 1,
        'max': 30,
        'label': 'Device change request expiry (days)',
        'used_by': 'FR-1.25'
    },
    'audit_retention_months': {
        'default': 36,
        'type': int,
        'min': 12,
        'max': 120,
        'label': 'Audit retention (months)',
        'used_by': 'FR-1.75'
    },
    'login_history_retention_months': {
        'default': 12,
        'type': int,
        'min': 3,
        'max': 36,
        'label': 'Login history retention (months)',
        'used_by': 'FR-1.49'
    },
    'notification_retention_days': {
        'default': 90,
        'type': int,
        'min': 30,
        'max': 365,
        'label': 'Notification retention (days)',
        'used_by': 'FR-1.64'
    },
    'current_policy_version': {
        'default': '1.0.0',
        'type': str,
        'label': 'Current policy version',
        'used_by': 'FR-1.81'
    },
    'geofence_min_radius_m': {
        'default': 20,
        'type': int,
        'min': 10,
        'max': 100,
        'label': 'Minimum geofence radius (meters)',
        'used_by': 'FR-2.35'
    },
    'geofence_max_radius_m': {
        'default': 2000,
        'type': int,
        'min': 100,
        'max': 5000,
        'label': 'Maximum geofence radius (meters)',
        'used_by': 'FR-2.35'
    },
    'max_shift_duration_minutes': {
        'default': 960,
        'type': int,
        'min': 240,
        'max': 1440,
        'label': 'Maximum shift duration (minutes)',
        'used_by': 'FR-2.65'
    },
    'agreement_expiry_notification_days': {
        'default': 30,
        'type': int,
        'min': 7,
        'max': 90,
        'label': 'Agreement expiry notification (days)',
        'used_by': 'FR-2.84'
    },
    'guard_min_age_years': {
        'default': 18,
        'type': int,
        'min': 18,
        'max': 25,
        'label': 'Guard minimum age (years)',
        'used_by': 'FR-3.21'
    },
    'employee_code_prefix': {
        'default': 'SEC-GRD',
        'type': str,
        'label': 'Employee code prefix',
        'used_by': 'FR-3.30'
    },
    'doc_expiry_alert_days': {
        'default': 30,
        'type': int,
        'min': 7,
        'max': 90,
        'label': 'Document expiry alert (days)',
        'used_by': 'FR-3.58'
    },
    'mandatory_doc_types': {
        'default': 'identity_proof,address_proof,police_verification,medical_fitness',
        'type': str,
        'label': 'Mandatory document types',
        'used_by': 'FR-3.13'
    },
    'mandatory_training_types': {
        'default': 'induction,fire_safety',
        'type': str,
        'label': 'Mandatory training types',
        'used_by': 'FR-3.69'
    },
    'service_request_code_prefix': {
        'default': 'SR',
        'type': str,
        'label': 'Service request prefix',
        'used_by': 'FR-4.37'
    },
    'quotation_code_prefix': {
        'default': 'QT',
        'type': str,
        'label': 'Quotation code prefix',
        'used_by': 'FR-4.85'
    },
    'max_negotiation_rounds': {
        'default': 3,
        'type': int,
        'min': 1,
        'max': 10,
        'label': 'Max quotation negotiation rounds',
        'used_by': 'FR-4.115'
    },
    'quotation_validity_days': {
        'default': 15,
        'type': int,
        'min': 3,
        'max': 60,
        'label': 'Standard quotation validity (days)',
        'used_by': 'FR-4.73'
    },
    'rolling_slot_window_days': {
        'default': 14,
        'type': int,
        'min': 1,
        'max': 90,
        'label': 'Rolling slot generation window (days)',
        'used_by': 'FR-5.2'
    },
    'min_rest_gap_hours': {
        'default': 8,
        'type': int,
        'min': 4,
        'max': 24,
        'label': 'Minimum rest gap between shifts (hours)',
        'used_by': 'FR-5.23'
    },
    'max_consecutive_days': {
        'default': 6,
        'type': int,
        'min': 1,
        'max': 14,
        'label': 'Max consecutive working days before warning',
        'used_by': 'FR-5.23'
    },
    'weekly_hours_warning_limit': {
        'default': 48,
        'type': int,
        'min': 20,
        'max': 84,
        'label': 'Weekly hours threshold for fatigue warning',
        'used_by': 'FR-5.23'
    },
    'daily_overtime_threshold_hours': {
        'default': 8.0,
        'type': float,
        'min': 4.0,
        'max': 16.0,
        'label': 'Daily overtime threshold hours',
        'used_by': 'FR-5.25'
    },
    'supervisor_future_edit_days': {
        'default': 7,
        'type': int,
        'min': 1,
        'max': 30,
        'label': 'Supervisor future edit window (days)',
        'used_by': 'FR-5.58'
    },
    'emergency_ratification_hours': {
        'default': 24,
        'type': int,
        'min': 1,
        'max': 72,
        'label': 'Emergency deployment ratification deadline (hours)',
        'used_by': 'FR-5.40'
    },
    # Module 6: Attendance Settings
    'check_in_window_before_mins': {
        'default': 30,
        'type': int,
        'min': 0,
        'max': 120,
        'label': 'Check-in window before shift start (minutes)',
        'used_by': 'FR-6.2'
    },
    'check_in_window_after_mins': {
        'default': 60,
        'type': int,
        'min': 0,
        'max': 240,
        'label': 'Check-in window after shift start (minutes)',
        'used_by': 'FR-6.2'
    },
    'late_grace_period_mins': {
        'default': 15,
        'type': int,
        'min': 0,
        'max': 60,
        'label': 'Late arrival grace period (minutes)',
        'used_by': 'FR-6.35'
    },
    'max_gps_accuracy_meters': {
        'default': 100.0,
        'type': float,
        'min': 10.0,
        'max': 500.0,
        'label': 'Maximum allowable GPS accuracy (meters)',
        'used_by': 'FR-6.7'
    },
    'device_time_mismatch_max_seconds': {
        'default': 300,
        'type': int,
        'min': 30,
        'max': 3600,
        'label': 'Device time mismatch threshold (seconds)',
        'used_by': 'FR-6.10'
    },
    'offline_sync_acceptance_hours': {
        'default': 24,
        'type': int,
        'min': 1,
        'max': 168,
        'label': 'Offline capture sync window (hours)',
        'used_by': 'FR-6.25'
    },
    'auto_close_delay_hours': {
        'default': 4,
        'type': int,
        'min': 1,
        'max': 24,
        'label': 'Missing check-out auto-close delay (hours)',
        'used_by': 'FR-6.18'
    },
    'no_show_delay_minutes': {
        'default': 60,
        'type': int,
        'min': 15,
        'max': 240,
        'label': 'No-show notification delay (minutes)',
        'used_by': 'FR-6.41'
    },
    'regularisation_window_days': {
        'default': 3,
        'type': int,
        'min': 1,
        'max': 30,
        'label': 'Guard regularisation request window (days)',
        'used_by': 'FR-6.55'
    },
    'manual_attendance_monthly_limit': {
        'default': 3,
        'type': int,
        'min': 1,
        'max': 10,
        'label': 'Monthly manual attendance limit per guard',
        'used_by': 'FR-6.58'
    },
    'large_correction_threshold_mins': {
        'default': 120,
        'type': int,
        'min': 30,
        'max': 480,
        'label': 'Correction size requiring Admin approval (minutes)',
        'used_by': 'FR-6.49'
    },
    'attendance_cutoff_day': {
        'default': 25,
        'type': int,
        'min': 1,
        'max': 31,
        'label': 'Monthly attendance period cut-off day',
        'used_by': 'FR-6.60'
    },
    'normal_update_interval_mins': {
        'default': 5,
        'type': int,
        'min': 1,
        'max': 60,
        'label': 'Normal tracking interval (minutes)',
        'used_by': 'FR-7.25'
    },
    'moving_update_interval_mins': {
        'default': 2,
        'type': int,
        'min': 1,
        'max': 30,
        'label': 'Moving tracking interval (minutes)',
        'used_by': 'FR-7.25'
    },
    'low_battery_interval_mins': {
        'default': 10,
        'type': int,
        'min': 2,
        'max': 60,
        'label': 'Low battery tracking interval (minutes)',
        'used_by': 'FR-7.25'
    },
    'stale_threshold_mins': {
        'default': 10,
        'type': int,
        'min': 2,
        'max': 60,
        'label': 'Stale telemetry threshold (minutes)',
        'used_by': 'FR-7.41'
    },
    'no_contact_threshold_mins': {
        'default': 20,
        'type': int,
        'min': 5,
        'max': 120,
        'label': 'No contact threshold (minutes)',
        'used_by': 'FR-7.41'
    },
    'geofence_debounce_count': {
        'default': 3,
        'type': int,
        'min': 1,
        'max': 10,
        'label': 'Geofence debounce consecutive readings',
        'used_by': 'FR-7.36'
    },
    'low_accuracy_threshold_meters': {
        'default': 50.0,
        'type': float,
        'min': 10.0,
        'max': 500.0,
        'label': 'Low GPS accuracy threshold (meters)',
        'used_by': 'FR-7.38'
    },
    'post_shift_cutoff_mins': {
        'default': 30,
        'type': int,
        'min': 5,
        'max': 180,
        'label': 'Post-shift tracking cutoff (minutes)',
        'used_by': 'FR-7.8'
    },
    'supervisor_ping_cooldown_mins': {
        'default': 5,
        'type': int,
        'min': 1,
        'max': 60,
        'label': 'Supervisor ping cooldown (minutes)',
        'used_by': 'FR-7.70'
    },
    'raw_location_retention_days': {
        'default': 30,
        'type': int,
        'min': 7,
        'max': 365,
        'label': 'Raw location points retention (days)',
        'used_by': 'FR-7.101'
    },
}

CACHE_TTL = 60  # Cache for 60 seconds (FR-1.89)
_LOCAL_CACHE = {}


def get_cache_key(company_id, key):
    return f"sys_setting:{company_id}:{key}"


def get_setting(key: str, company_id=None):
    """
    Reads a system setting with caching of at most 60 seconds.
    Falls back to default if not set.
    """
    if key not in SETTING_DEFINITIONS:
        raise KeyError(f"Unknown system setting: {key}")

    defn = SETTING_DEFINITIONS[key]

    if company_id is None:
        first_comp = Company.objects.first()
        if first_comp:
            company_id = str(first_comp.company_id)
        else:
            return defn['default']

    cache_key = get_cache_key(company_id, key)
    cached = _LOCAL_CACHE.get(cache_key)
    now = time.time()
    if cached and (now - cached['ts']) < CACHE_TTL:
        return cached['val']

    try:
        setting = SystemSetting.objects.filter(company_id=company_id, key=key).first()
        if setting:
            val = defn['type'](setting.value)
        else:
            val = defn['default']
    except Exception as e:
        logger.error(f"Error fetching setting {key}: {e}")
        val = defn['default']

    _LOCAL_CACHE[cache_key] = {'val': val, 'ts': now}
    return val


def validate_setting_value(key: str, raw_value):
    """
    Validates a setting against its definition and range.
    Returns the parsed value or raises ValueError.
    """
    if key not in SETTING_DEFINITIONS:
        raise ValueError(f"Unknown system setting '{key}'.")

    defn = SETTING_DEFINITIONS[key]
    val_type = defn['type']

    try:
        val = val_type(raw_value)
    except (ValueError, TypeError):
        raise ValueError(f"Value for {key} must be of type {val_type.__name__}.")

    if 'min' in defn and val < defn['min']:
        raise ValueError(translate('settings.value_out_of_range', min=defn['min'], max=defn.get('max', '∞')))
    if 'max' in defn and val > defn['max']:
        raise ValueError(translate('settings.value_out_of_range', min=defn.get('min', '-∞'), max=defn['max']))

    return val


def set_setting(company_id, key: str, raw_value, user=None, reason=None):
    """
    Updates a system setting, writes audit, and invalidates cache.
    Applies within 60s (FR-1.89).
    """
    from foundation.services.audit_service import write_audit_event

    val = validate_setting_value(key, raw_value)
    defn = SETTING_DEFINITIONS[key]

    setting, created = SystemSetting.objects.get_or_create(
        company_id=company_id,
        key=key,
        defaults={'value': str(val), 'updated_by': user}
    )

    old_val = defn['type'](setting.value) if not created else None
    if not created:
        setting.value = str(val)
        setting.updated_by = user
        setting.save()

    # Invalidate cache
    cache_key = get_cache_key(company_id, key)
    _LOCAL_CACHE.pop(cache_key, None)

    # Audit event (settings.changed)
    write_audit_event(
        action_code='settings.changed',
        actor_user=user,
        module='foundation',
        record_type='SystemSetting',
        record_id=str(setting.setting_id),
        old_values={'key': key, 'value': old_val} if old_val is not None else None,
        new_values={'key': key, 'value': val},
        reason=reason,
        result='SUCCESS',
        company_id=company_id
    )

    return val


def initialize_default_settings(company):
    """
    Seeds default system settings for a company if not already set.
    """
    for key, defn in SETTING_DEFINITIONS.items():
        SystemSetting.objects.get_or_create(
            company=company,
            key=key,
            defaults={'value': str(defn['default'])}
        )

