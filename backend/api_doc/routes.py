"""
API Documentation Routes
Serves the API documentation web pages
"""

from flask import Blueprint, render_template, request

# Create blueprint for API documentation
api_docs = Blueprint(
    'api_docs',
    __name__,
    template_folder='templates',
    static_folder='static',
    static_url_path='/docs/static'
)

def get_base_url():
    """Get the base URL for API requests"""
    # Use the request's host if available, otherwise default
    if request:
        scheme = request.scheme
        host = request.host
        return f"{scheme}://{host}"
    return "http://localhost:5001"

@api_docs.route('/')
@api_docs.route('/docs')
@api_docs.route('/docs/')
def api_docs_home():
    """API Documentation home page (overview)"""
    return render_template('overview.html', base_url=get_base_url())

@api_docs.route('/docs/reference')
def api_docs_reference():
    """API Reference page with detailed endpoint documentation"""
    return render_template('reference.html', base_url=get_base_url())

@api_docs.route('/docs/examples')
def api_docs_examples():
    """API Examples page with code samples"""
    return render_template('examples.html', base_url=get_base_url())

# Static file serving is handled automatically by Flask through the blueprint
