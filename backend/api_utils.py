"""API response formatting utilities for standardized responses"""


def success_response(data, meta=None):
    """
    Format a successful API response
    
    Args:
        data: The response data
        meta: Optional metadata (pagination info, etc.)
        
    Returns:
        Dictionary with standardized success response format
    """
    response = {
        'success': True,
        'data': data,
        'error': None
    }
    
    if meta:
        response['meta'] = meta
    
    return response


def error_response(code, message, status_code=400):
    """
    Format an error API response
    
    Args:
        code: Error code identifier
        message: Human-readable error message
        status_code: HTTP status code (default: 400)
        
    Returns:
        Tuple of (response dict, status code)
    """
    response = {
        'success': False,
        'data': None,
        'error': {
            'code': code,
            'message': message
        }
    }
    
    return response, status_code


def paginated_response(items, page, limit, total):
    """
    Format a paginated API response
    
    Args:
        items: List of items for current page
        page: Current page number
        limit: Items per page
        total: Total number of items
        
    Returns:
        Dictionary with standardized paginated response
    """
    total_pages = (total + limit - 1) // limit if limit > 0 else 1
    
    return success_response(
        data=items,
        meta={
            'page': page,
            'limit': limit,
            'total': total,
            'total_pages': total_pages,
            'has_next': page < total_pages,
            'has_prev': page > 1
        }
    )


def validate_pagination_params(page, limit, max_limit=1000):
    """
    Validate and normalize pagination parameters
    
    Args:
        page: Page number (string or int)
        limit: Items per page (string or int)
        max_limit: Maximum allowed limit
        
    Returns:
        Tuple of (validated_page, validated_limit) or raises ValueError
    """
    try:
        page = int(page) if page else 1
        limit = int(limit) if limit else 50
    except (ValueError, TypeError):
        raise ValueError('Invalid pagination parameters')
    
    # Validate ranges
    if page < 1:
        raise ValueError('Page must be >= 1')
    
    if limit < 1:
        raise ValueError('Limit must be >= 1')
    
    if limit > max_limit:
        raise ValueError(f'Limit cannot exceed {max_limit}')
    
    return page, limit


def validate_date_param(date_str, param_name='date'):
    """
    Validate date parameter in ISO format (YYYY-MM-DD)
    
    Args:
        date_str: Date string to validate
        param_name: Name of parameter (for error messages)
        
    Returns:
        Validated date string or raises ValueError
    """
    if not date_str:
        return None
    
    from datetime import datetime
    
    try:
        # Try parsing as ISO date
        datetime.fromisoformat(date_str)
        return date_str
    except (ValueError, TypeError):
        raise ValueError(f'Invalid {param_name} format. Use YYYY-MM-DD or ISO format')


def validate_enum_param(value, allowed_values, param_name='parameter'):
    """
    Validate that a parameter is one of allowed values
    
    Args:
        value: Value to validate
        allowed_values: List of allowed values
        param_name: Name of parameter (for error messages)
        
    Returns:
        Validated value or raises ValueError
    """
    if not value:
        return None
    
    if value not in allowed_values:
        allowed_str = ', '.join(allowed_values)
        raise ValueError(f'Invalid {param_name}. Must be one of: {allowed_str}')
    
    return value
