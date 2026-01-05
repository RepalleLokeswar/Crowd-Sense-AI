import cv2
from re_id import Config

def calculate_centroid(x1,y1,x2,y2):
    return int((x1+x2)/2), int((y1+y2)/2)

def point_inside_rectangle(p, r):
    px,py = p; x1,y1,x2,y2 = r
    return x1<=px<=x2 and y1<=py<=y2

class Zone:
    def __init__(self,id,coords,color):
        self.id=id
        self.coords=coords
        self.color=color
        self.total_count=0 # Renamed cumulative
        self.counted_ids=set()
        self.active_ids=set()
        self.prev={}

        # Hysteresis: Track how long an ID has been outside after being counted
        self.frames_outside={}
        self.HYSTERESIS_THRESHOLD = 30  # Frames to wait before allowing re-count

    @property
    def count(self):
        return len(self.active_ids)

    def is_inside(self,p):
        return point_inside_rectangle(p,self.coords)

    def count_entry(self,gid,centroid):
        # Ignore unconfirmed (negative) IDs
        if gid < 0:
            return

        inside=self.is_inside(centroid)
        
        # 1. Handle Entry
        if inside:
            # Reset outside counter since they are inside
            if gid in self.frames_outside:
                self.frames_outside.pop(gid)
            
            # Count if not already counted for this session
            if gid not in self.active_ids:
                self.active_ids.add(gid)
                # Only increment total if never counted (or re-allowed)
                if gid not in self.counted_ids:
                    self.total_count+=1
                    self.counted_ids.add(gid)
                
                print(f"✓ ID {gid} ENTERED {self.id} → Live: {self.count}")
        
        # 2. Handle Exit / Debounce
        else: # Outside
            if gid in self.active_ids:
                self.active_ids.discard(gid)
                print(f"× ID {gid} LEFT {self.id} → Live: {self.count}")
            
            # Only track exit duration if they were previously counted
            if gid in self.counted_ids:
                curr_frames = self.frames_outside.get(gid, 0)
                self.frames_outside[gid] = curr_frames + 1
                
                # If outside long enough, forget them (allow re-count)
                if self.frames_outside[gid] > self.HYSTERESIS_THRESHOLD:
                    self.counted_ids.discard(gid)
                    self.frames_outside.pop(gid)

        self.prev[gid]=inside

    def remove_id(self,gid):
        self.active_ids.discard(gid)
        self.prev.pop(gid,None)

    def draw(self,frame):
        # Ensure coords are ints
        x1, y1, x2, y2 = map(int, self.coords)
        cv2.rectangle(frame,(x1,y1),(x2,y2),self.color,2)
        
        # Format: "ZoneName: 5"
        label = f"{self.id}: {self.count}"
        
        # Smart Positioning: If box is at top, draw text inside/below
        text_y = y1 - 10
        if text_y < 20: 
            text_y = y1 + 25
            
        # Draw Black Outline for visibility
        cv2.putText(frame, label, (x1, text_y), Config.FONT, 0.7, (0,0,0), 4)
        # Draw Colored Text
        cv2.putText(frame, label, (x1, text_y), Config.FONT, 0.7, self.color, 2)
