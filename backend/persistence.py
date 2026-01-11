import time
import threading
import datetime
from .state import state
from .extensions import db
from .models import AnalyticsData

def start_persistence_thread(app, interval=60):
    """
    Starts a background thread to save analytics data to the database.
    Requires the Flask 'app' object to create an application context.
    """
    def persistence_loop():
        print("DEBUG: Persistence Thread Started.")
        while True:
            try:
                # Sleep first (or specific interval)
                time.sleep(interval)
                
                # Check stop signal
                if state.stop_event.is_set():
                    print("DEBUG: Persistence Thread Stopping...")
                    break

                # Get Current Data
                data = state.get_data()
                live_count = data.get('people_count', 0)
                
                # Create DB Record
                with app.app_context():
                    record = AnalyticsData(
                        zone_name='_GLOBAL_OCCUPANCY_',
                        count=live_count,
                        timestamp=datetime.datetime.now()
                    )
                    db.session.add(record)
                    
                    # Optional: Save per-zone stats if needed
                    # zones = data.get('zones', {})
                    # ... logic to iterate zones ...
                    
                    db.session.commit()
                    # print(f"DEBUG: Saved Analytics Snapshot: {live_count}")
                    
                # Save Alerts
                pending = state.get_and_clear_alerts()
                if pending:
                    from .models import Alert
                    count_saved = 0
                    for a in pending:
                         new_alert = Alert(
                             zone_name=a['zone_name'],
                             message=a['message'],
                             # timestamp=a['timestamp'] # Use DB server time or convert
                         )
                         db.session.add(new_alert)
                         count_saved += 1
                    
                    if count_saved > 0:
                        db.session.commit()
                        print(f"DEBUG: Saved {count_saved} alerts to DB.")

            except Exception as e:
                print(f"ERROR: Persistence Loop Failed: {e}")
                time.sleep(5) # Backoff

    t = threading.Thread(target=persistence_loop, daemon=True)
    t.start()
