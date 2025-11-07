# gunicorn.conf.py
# Gunicorn configuration file

import logging
import os

# Logging
accesslog = '-'  # Log to stdout
errorlog = '-'   # Log to stderr
loglevel = 'info'

# Worker configuration
workers = 1
worker_class = 'sync'
timeout = 120

# Server mechanics
daemon = False
pidfile = None
umask = 0
user = None
group = None
tmp_upload_dir = None

# Hooks
def post_worker_init(worker):
    """
    Called after a worker has been forked and initialized.
    This is where we should start the research worker thread.
    """
    logger = logging.getLogger(__name__)
    logger.info(f"=== Post-worker init hook called for worker PID {os.getpid()} ===")
    
    try:
        # Import modules here (in worker process)
        import research_queue
        import song_research
        
        # Start the worker thread
        if not research_queue._worker_running:
            research_queue.start_worker(song_research.research_song)
            logger.info(f"Research worker thread initialized in gunicorn worker PID {os.getpid()}")
        else:
            logger.warning(f"Worker thread already running in PID {os.getpid()}")
            
    except Exception as e:
        logger.error(f"Error initializing research worker in gunicorn worker: {e}", exc_info=True)


def worker_exit(server, worker):
    """
    Called when a worker exits.
    """
    logger = logging.getLogger(__name__)
    logger.info(f"Worker {worker.pid} exiting - stopping research worker")
    
    try:
        import research_queue
        research_queue.stop_worker()
    except Exception as e:
        logger.error(f"Error stopping research worker: {e}")