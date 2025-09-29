from flask import Blueprint, render_template_string

test_bp = Blueprint('test', __name__)

@test_bp.route('/test-auth-user')
def test_auth_user():
    """Тестовая страница для проверки функции get_auth_user_data"""
    template = '''
    <!DOCTYPE html>
    <html>
    <head>
        <title>Test Auth User Data</title>
    </head>
    <body>
        <h1>Test Auth User Data</h1>
        {% set auth_user = get_auth_user_data() %}
        <p>auth_user = {{ auth_user }}</p>
        {% if auth_user %}
            <p>Username: {{ auth_user.username }}</p>
            <p>Full Name: {{ auth_user.full_name }}</p>
            <p>Short Name: {{ auth_user.short_name }}</p>
        {% else %}
            <p>No auth user data</p>
        {% endif %}
    </body>
    </html>
    '''
    return render_template_string(template)