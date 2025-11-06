"""
Research Queue Module
Manages background processing queue for song research tasks
"""

import queue
import threading
import logging
from typing import Optional

logger = logging.getLogger(__name__)

# Global task queue - thread-safe
research_queue = queue.Queue()

# Flag to control worker thread
_worker_running = False
_worker_thread: Optional[threading.Thread] = None


def add_song_to_queue(song_id: str, song_name: str) -> bool:
    """
    Add a song to the research queue
    
    Args:
        song_id: UUID of the song
        song_name: Name of the song
        
    Returns:
        True if successfully queued, False otherwise
    """
    import os
    try:
        research_queue.put({
            'song_id': song_id,
            'song_name': song_name
        })
        logger.info(f"Queued song for research: {song_id} / {song_name}")
        logger.info(f"  Queue size after add: {research_queue.qsize()}")
        logger.info(f"  Process ID: {os.getpid()}")
        logger.info(f"  Worker running flag: {_worker_running}")
        logger.info(f"  Worker thread: {_worker_thread}")
        return True
    except Exception as e:
        logger.error(f"Error queuing song {song_id}: {e}")
        return False


def get_queue_size() -> int:
    """Get the current size of the research queue"""
    return research_queue.qsize()


def start_worker(research_function):
    """
    Start the background worker thread
    
    Args:
        research_function: Function to call for each song (takes song_id, song_name)
    """
    global _worker_running, _worker_thread
    
    if _worker_running:
        logger.warning("Worker thread already running")
        return
    
    _worker_running = True
    _worker_thread = threading.Thread(
        target=_worker_loop,
        args=(research_function,),
        daemon=True,
        name="ResearchWorker"
    )
    _worker_thread.start()
    logger.info("Research worker thread started")


def stop_worker():
    """Stop the background worker thread"""
    global _worker_running
    
    if not _worker_running:
        return
    
    logger.info("Stopping research worker thread...")
    _worker_running = False
    
    # Add poison pill to unblock queue.get()
    research_queue.put(None)
    
    if _worker_thread:
        _worker_thread.join(timeout=5.0)
    
    logger.info("Research worker thread stopped")


def _worker_loop(research_function):
    """
    Main worker loop - processes songs from the queue
    
    Args:
        research_function: Function to call for each song
    """
    import os
    try:
        logger.info("=== Worker loop starting ===")
        logger.info(f"Process ID: {os.getpid()}")
        logger.info(f"Thread ID: {threading.current_thread().ident}")
        logger.info(f"Thread name: {threading.current_thread().name}")
        logger.info(f"_worker_running at start: {_worker_running}")
        logger.info(f"research_function: {research_function}")
        
        iteration = 0
        while _worker_running:
            iteration += 1
            
            # Log heartbeat every 30 seconds (30 iterations of 1 second timeout)
            if iteration % 30 == 1:
                logger.info(f"Worker heartbeat - iteration {iteration}, still running")
            
            try:
                # Get next song from queue (blocks until available)
                song_data = research_queue.get(timeout=1.0)
                
                logger.info(f"!!! Got item from queue: {song_data}")
                
                # Check for poison pill
                if song_data is None:
                    logger.info("Received poison pill - exiting")
                    break
                
                song_id = song_data['song_id']
                song_name = song_data['song_name']
                
                logger.info(f"Processing queued song: {song_id} / {song_name}")
                
                # Call the research function
                try:
                    logger.info(f"Calling research_function({song_id}, {song_name})")
                    research_function(song_id, song_name)
                    logger.info(f"Successfully completed research for {song_id}")
                except Exception as e:
                    logger.error(f"Error researching song {song_id}: {e}", exc_info=True)
                
                # Mark task as done
                research_queue.task_done()
                logger.info(f"Marked task as done for {song_id}")
                
            except queue.Empty:
                # No items in queue, continue waiting
                continue
            except Exception as e:
                logger.error(f"Error in worker loop iteration {iteration}: {e}", exc_info=True)
                # Continue running even if one iteration fails
                continue
        
        logger.info(f"=== Worker loop exited normally after {iteration} iterations ===")
        logger.info(f"_worker_running at exit: {_worker_running}")
        
    except Exception as e:
        logger.error(f"!!! FATAL ERROR in worker loop: {e}", exc_info=True)
        logger.error("Worker thread is terminating due to unhandled exception")
    finally:
        logger.info("Worker thread finally block executed")