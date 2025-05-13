from functools import wraps
from flask import session, redirect, url_for, flash, request, jsonify

def staff_required(f):
    """Decorator to require staff authentication for a route."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('is_staff'):
            flash('Please log in as staff to access this page.', 'error')
            if request.is_xhr:
                return jsonify({'error': 'Please log in as staff'}), 401
            return redirect(url_for('main.staff_login'))
        return f(*args, **kwargs)
    return decorated_function 