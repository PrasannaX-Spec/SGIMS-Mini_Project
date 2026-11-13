from rest_framework.views import exception_handler
from rest_framework.response import Response


def custom_exception_handler(exc, context):
    """
    Standardizes error responses across DRF endpoints.
    Format: {"detail": "...", "code": "...", "errors": {...}}
    """
    response = exception_handler(exc, context)

    if response is not None:
        data = response.data
        if isinstance(data, dict):
            detail = data.get('detail')
            
            # Extract code reliably
            code = None
            if hasattr(exc, 'detail') and hasattr(exc.detail, 'code'):
                code = exc.detail.code
            elif hasattr(exc, 'code'):
                code = exc.code
            elif 'code' in data:
                code = data['code']
            else:
                code = getattr(exc, 'default_code', 'ERROR')

            # Ensure 'detail' and 'code' are present
            if not detail and 'non_field_errors' in data:
                detail = data['non_field_errors'][0] if isinstance(data['non_field_errors'], list) else data['non_field_errors']

            response.data = {
                'detail': str(detail) if detail else 'An error occurred.',
                'code': str(code).upper(),
                'errors': {k: v for k, v in data.items() if k not in ('detail', 'code')} if any(k not in ('detail', 'code') for k in data) else None
            }
        elif isinstance(data, list):
            response.data = {
                'detail': data[0] if data else 'An error occurred.',
                'code': 'VALIDATION_ERROR',
                'errors': data
            }

    return response
