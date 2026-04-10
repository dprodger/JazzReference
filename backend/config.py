"""
Configuration Module for Jazz Reference API
Handles logging setup and Flask app initialization
"""

import os
import re
import logging


# ============================================================================
# CREDENTIAL SCRUBBING FOR LOGS
# ============================================================================
#
# psycopg and libpq occasionally echo the full connection string (DSN) into
# exception messages. If those exceptions are logged via f-strings, the
# database password ends up in log output. The filter below redacts any DSN
# passwords and `password=...` key-value forms from log records before they
# reach a handler. It's defense-in-depth — callers don't have to remember to
# scrub anything, and it also covers third-party libraries that log via the
# standard logging module.

_CREDENTIAL_PATTERNS = (
    # postgresql://user:password@host  →  postgresql://user:***@host
    (re.compile(r'(postgres(?:ql)?://[^:/@\s]+:)[^@\s]+(@)'), r'\1***\2'),
    # password='secret'  →  password='***'
    (re.compile(r"(password\s*=\s*)'[^']*'"), r"\1'***'"),
    # password="secret"  →  password="***"
    (re.compile(r'(password\s*=\s*)"[^"]*"'), r'\1"***"'),
    # password=secret    →  password=***  (unquoted, up to whitespace)
    (re.compile(r'(password\s*=\s*)[^\s\'"][^\s]*'), r'\1***'),
)


def _scrub_credentials(text):
    """Mask database passwords in an arbitrary string."""
    if text is None:
        return text
    s = str(text)
    for pattern, replacement in _CREDENTIAL_PATTERNS:
        s = pattern.sub(replacement, s)
    return s


class CredentialScrubFilter(logging.Filter):
    """
    Logging filter that removes database passwords from log records.

    Scrubs both ``record.msg`` (for f-string style logging) and any string
    entries in ``record.args`` (for %-style logging). Non-string args are
    passed through unchanged so that exception objects, numbers, etc. are
    not coerced prematurely.
    """

    def filter(self, record):
        if isinstance(record.msg, str):
            record.msg = _scrub_credentials(record.msg)
        if record.args:
            if isinstance(record.args, dict):
                record.args = {
                    k: (_scrub_credentials(v) if isinstance(v, str) else v)
                    for k, v in record.args.items()
                }
            elif isinstance(record.args, tuple):
                record.args = tuple(
                    _scrub_credentials(a) if isinstance(a, str) else a
                    for a in record.args
                )
        return True


def configure_logging():
    """
    Configure application logging with standard format.

    Installs a credential-scrubbing filter on the root logger's handlers so
    that any log record passing through them has database passwords masked.

    Returns:
        Logger instance for the config module
    """
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    scrub_filter = CredentialScrubFilter()
    for handler in logging.getLogger().handlers:
        # Avoid adding the filter twice if configure_logging() is called again.
        if not any(isinstance(f, CredentialScrubFilter) for f in handler.filters):
            handler.addFilter(scrub_filter)

    return logging.getLogger(__name__)


def init_app_config(app):
    """
    Initialize Flask app configuration
    
    This sets up:
    - Custom JSON provider for date formatting
    
    Args:
        app: Flask application instance
    """
    from utils.json_provider import CustomJSONProvider
    app.json = CustomJSONProvider(app)


def set_db_pooling_mode():
    """
    Set database pooling mode environment variable
    
    This MUST be called before importing db_utils to ensure
    the connection pool is configured correctly.
    """
    os.environ['DB_USE_POOLING'] = 'true'