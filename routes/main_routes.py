"""Основные маршруты приложения"""

from flask import Blueprint, render_template, redirect, url_for
from .auth_routes import get_current_user

main_bp = Blueprint('main', __name__)


@main_bp.route('/')
def home():
    """Маршрут для главной страницы."""
    return redirect(url_for('main.main'))


@main_bp.route('/main', methods=['GET'])
def main():
    """Маршрут для главной страницы после входа в систему."""
    user = get_current_user()
    return render_template('main.html', current_user=user)


@main_bp.route('/menu')
def menu():
    """Маршрут для страницы меню."""
    user = get_current_user()
    return render_template('menu.html', current_user=user)
