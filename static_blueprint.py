"""
Blueprint for serving static files when using PrefixMiddleware
"""
from flask import Blueprint, send_from_directory, current_app
import os

static_bp = Blueprint('static_files', __name__)

@static_bp.route('/static/<path:filename>')
def static_files(filename):
    """Serve static files"""
    return send_from_directory(current_app.static_folder, filename)

@static_bp.route('/static/css/<path:filename>')
def static_css(filename):
    """Serve CSS files"""
    css_folder = os.path.join(current_app.static_folder, 'css')
    return send_from_directory(css_folder, filename)

@static_bp.route('/static/js/<path:filename>')
def static_js(filename):
    """Serve JS files"""
    js_folder = os.path.join(current_app.static_folder, 'js')
    return send_from_directory(js_folder, filename)

@static_bp.route('/static/img/<path:filename>')
def static_img(filename):
    """Serve image files"""
    print(f"🖼️ Static IMG request: {filename}")
    img_folder = os.path.join(current_app.static_folder, 'img')
    print(f"🖼️ Static folder: {img_folder}")
    print(f"🖼️ File exists: {os.path.exists(os.path.join(img_folder, filename))}")
    return send_from_directory(img_folder, filename)