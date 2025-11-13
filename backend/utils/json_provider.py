# utils/json_provider.py
from datetime import date
from flask.json.provider import DefaultJSONProvider

class CustomJSONProvider(DefaultJSONProvider):
    """Custom JSON provider that formats dates as YYYY-MM-DD"""
    def default(self, obj):
        if isinstance(obj, date):
            return obj.strftime('%Y-%m-%d')
        return super().default(obj)