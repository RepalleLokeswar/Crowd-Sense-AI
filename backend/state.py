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
        
        # High-Res History for Chart Stability (Last 60 points ~ 30-60s)
        from collections import deque
        self.history = deque(maxlen=100)
        
        self.pending_alerts = [] # Queue for new alerts to be saved to DB

    def add_alert(self, zone_name, message):
        with self.lock:
             # Add simple duplication check or max size check if needed
             self.pending_alerts.append({
                 "zone_name": zone_name,
                 "message": message,
                 "timestamp": time.time()
             })

    def get_and_clear_alerts(self):
        with self.lock:
            alerts = list(self.pending_alerts)
            self.pending_alerts.clear()
            return alerts

    def update(self, data):
        with self.lock:
            self.live_data.update(data)
            
            # Append to history if count is present
            if "people_count" in data:
                import datetime
                now_str = datetime.datetime.now().strftime('%H:%M:%S')
                
                # Check previous to prevent duplicates (1 point per second max)
                if not self.history or self.history[-1]['time'] != now_str:
                    self.history.append({
                        "time": now_str,
                        "count": data["people_count"]
                    })
            
            # Inject alert count into live data for immediate frontend feedback
            # Note: This is transient "new" alerts, total alert count is separate
            self.live_data['new_alerts'] = len(self.pending_alerts)
            
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

    def get_history(self):
        with self.lock:
            return list(self.history)

    # Frame Buffer Methods
    def update_frame(self, cam_id, frame_bytes):
        with self.lock:
            if not hasattr(self, 'frame_buffer'):
                self.frame_buffer = {}
            if not hasattr(self, 'frame_events'):
                self.frame_events = {}
            
            self.frame_buffer[str(cam_id)] = frame_bytes
            
            # Notify waiters
            if str(cam_id) not in self.frame_events:
                self.frame_events[str(cam_id)] = threading.Condition(self.lock)
            
            self.frame_events[str(cam_id)].notify_all()

    def get_frame(self, cam_id):
        with self.lock:
            if not hasattr(self, 'frame_buffer'):
                return None
            return self.frame_buffer.get(str(cam_id))

    def wait_for_frame(self, cam_id, timeout=1.0):
        with self.lock:
            if not hasattr(self, 'frame_events'):
                self.frame_events = {}
            
            if str(cam_id) not in self.frame_events:
                self.frame_events[str(cam_id)] = threading.Condition(self.lock)
            
            # Wait for notification
            self.frame_events[str(cam_id)].wait(timeout)
            
            if hasattr(self, 'frame_buffer'):
                return self.frame_buffer.get(str(cam_id))
            return None

# Global Singleton
state = SystemState()
