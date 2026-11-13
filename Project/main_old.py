import cv2
import numpy as np
from fastapi import FastAPI, Request
from fastapi.responses import StreamingResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel


app = FastAPI()

# Link the HTML and CSS folders
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# Global variables that the HTML sliders will update
settings = {
    "blur_kernel": 3,
    "threshold": 105,
    "min_area": 50
}

# 1. SERVE THE HTML PAGE
@app.get("/")
async def index(request: Request):
    return templates.TemplateResponse(request, "index.html")

# 2. RECEIVE SLIDER UPDATES FROM JAVASCRIPT
class SettingsUpdate(BaseModel):
    blur_kernel: int
    threshold: int
    min_area: int

@app.post("/update_settings")
async def update_settings(new_settings: SettingsUpdate):
    settings["blur_kernel"] = new_settings.blur_kernel
    settings["threshold"] = new_settings.threshold
    settings["min_area"] = new_settings.min_area
    return {"status": "success"}

# 3. OPENCV VIDEO GENERATOR
def generate_frames(feed_type="normal"):
    cap = cv2.VideoCapture(0) # Open webcam
    
    try:
        while True:
            success, frame = cap.read()
            if not success:
                break
                
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            blur = cv2.GaussianBlur(gray, (settings["blur_kernel"], settings["blur_kernel"]), 0)
            _, thresh = cv2.threshold(blur, settings["threshold"], 255, cv2.THRESH_BINARY)
            
            # Draw boxes on the normal frame
            if feed_type == "normal":
                contours, _ = cv2.findContours(thresh, cv2.RETR_LIST, cv2.CHAIN_APPROX_NONE)
                count = 0
                for cnt in contours:
                    if cv2.contourArea(cnt) > settings["min_area"]:
                        count += 1
                        x, y, w, h = cv2.boundingRect(cnt)
                        cv2.rectangle(frame, (x, y), (x + w, y + h), (0, 255, 0), 2)
                
                cv2.putText(frame, f"COUNT: {count}", (20, 40), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
                ret, buffer = cv2.imencode('.jpg', frame)
            
            # Send just the black & white mask
            else:
                ret, buffer = cv2.imencode('.jpg', thresh)
                
            frame_bytes = buffer.tobytes()
            
            # Yield the frame in byte format for the browser
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')
    finally:
        cap.release()

# 4. STREAMING ENDPOINTS
@app.get("/video_feed")
def video_feed():
    # Feeds the color AR feed to Screen 1
    return StreamingResponse(generate_frames("normal"), media_type="multipart/x-mixed-replace; boundary=frame")

@app.get("/mask_feed")
def mask_feed():
    # Feeds the B&W mask to Screen 2
    return StreamingResponse(generate_frames("mask"), media_type="multipart/x-mixed-replace; boundary=frame")