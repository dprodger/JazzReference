# API Documentation

This directory contains the web-based documentation for the Jazz Reference API.

## Structure

```
api_doc/
├── __init__.py          # Module initialization
├── routes.py            # Flask routes for documentation pages
├── templates/           # HTML templates
│   ├── base.html       # Base template with header/footer
│   ├── overview.html   # Overview/home page
│   ├── reference.html  # Detailed API reference
│   └── examples.html   # Code examples and use cases
└── static/             # Static assets
    ├── css/
    │   └── style.css   # Styling for documentation
    └── js/
        └── main.js     # Interactive features (copy buttons, etc.)
```

## Usage

The documentation is automatically integrated into the main Flask application. Access it at:

- **Overview**: `/docs` or `/docs/`
- **API Reference**: `/docs/reference`
- **Examples**: `/docs/examples`

## Features

- Clean, professional design
- Syntax-highlighted code examples
- Interactive "Copy" buttons for code blocks
- Responsive layout for mobile devices
- Multiple language examples (JavaScript, Python, Swift, cURL)
- Comprehensive endpoint documentation
- Real-world use case examples

## Integration

The documentation is integrated into the main Flask app via a Blueprint. See the main app.py file for the integration code.

## Maintenance

To update the documentation:

1. **Modify templates** in `templates/` for content changes
2. **Update styles** in `static/css/style.css` for design changes
3. **Add interactivity** in `static/js/main.js` for new features
4. **Add routes** in `routes.py` for new documentation pages
