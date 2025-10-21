# Gunicorn configuration for Render deployment
# This limits workers to prevent exceeding Supabase connection limits

import multiprocessing

# Worker configuration
# Use only 1 worker to minimize database connections
# Each worker creates its own connection pool (1-2 connections)
workers = 1

# Worker class
worker_class = 'sync'

# Timeout (seconds) - increase to prevent worker timeouts during DB connection issues
timeout = 60

# Logging
accesslog = '-'
errorlog = '-'
loglevel = 'info'

# Graceful timeout
graceful_timeout = 30

# Keep alive
keepalive = 5

# Preload app
preload_app = False  # Don't preload to avoid connection issues

# Maximum requests per worker (helps with memory leaks)
max_requests = 1000
max_requests_jitter = 50