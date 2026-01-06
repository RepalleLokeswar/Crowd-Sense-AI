import threading

class SystemState:
    def __init__(self):
        self.lock = threading.Lock()
        
        # Core State
        self.live_data = {
            "live_count": 0,
            "people_count": 0,
            "total_visitors": 0,
            "zones": {},
            "cameras": {},
            "alert_count": 0,
            "active_cameras": 0
        }
        
        self.command_queue = []
        self.command_queue = []
        self.stop_event = threading.Event()
        self.detection_thread = None # Handle to current thread
        
    def update(self, data):
        with self.lock:
            self.live_data.update(data)
            
    def get_data(self):
        with self.lock:
            return self.live_data.copy()
            
    def queue_command(self, cmd):
        with self.lock:
            self.command_queue.append(cmd)
            
    def get_and_clear_commands(self):
        with self.lock:
            cmds = list(self.command_queue)
            self.command_queue.clear()
            return cmds

# Global Singleton
state = SystemState()
