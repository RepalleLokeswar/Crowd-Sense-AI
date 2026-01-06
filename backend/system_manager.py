import threading
import os
import sys
from .state import state

def start_unified_detection(source="0"):
    """
    Starts the detection loop as a background thread.
    Handles restarting if previously stopped.
    """
    # 1. Check if already running
    if state.detection_thread and state.detection_thread.is_alive():
        if not state.stop_event.is_set():
            print("DEBUG: Detection is already running.")
            return "System is already running."
        else:
            # Thread is alive but stop signal is set? 
            # It should be shutting down. We can't easily restart until it dies.
            # But let's assume if user clicks Start, they want to reset.
            print("DEBUG: Thread alive but stop set. Clearing stop to resume or restart.")
            state.stop_event.clear()
            return "Resumed/Restarting..."

    # 2. Reset Stop Signal (Crucial for Restart)
    state.stop_event.clear()

    # 3. Setup Import Path for main.py (in Root)
    # This assumes backend/system_manager.py -> .. -> Root
    root_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
    if root_path not in sys.path:
        sys.path.append(root_path)

    try:
        from main import run_detection_headless
    except ImportError as e:
        return f"Failed to import main detection process: {e}"

    # 4. Start Thread
    try:
        # Pass state_manager so main.py uses shared memory
        t = threading.Thread(
            target=run_detection_headless, 
            kwargs={
                "args_source": source, 
                "state_manager": state, 
                "headless": True
            }
        )
        t.daemon = True # Daemon thread dies when App dies
        t.start()
        
        state.detection_thread = t
        print(f"DEBUG: Detection Thread Launched (Source: {source})")
        return "Detection Started"
    except Exception as e:
        print(f"ERROR: Failed to launch thread: {e}")
        return f"Error triggering detection: {e}"
