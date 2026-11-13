import os, time, threading, collections, shutil
import cv2
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.responses import StreamingResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

BASE = os.path.dirname(os.path.abspath(__file__))
UPLOAD_DIR = os.path.join(BASE, "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)

app = FastAPI()
app.mount("/static", StaticFiles(directory=os.path.join(BASE, "static")), name="static")

state = {"blur": 3, "threshold": 105, "min_area": 50, "live": 0,
         "hist": collections.deque(maxlen=30), "video": False}
latest = {"normal": None, "mask": None}
lock = threading.Lock()
cap = cv2.VideoCapture(0)

class Params(BaseModel):
    blur: int
    threshold: int
    min_area: int

class Source(BaseModel):
    source: int = 0

def worker():
    while True:
        with lock:
            ok, frame = cap.read() if cap.isOpened() else (False, None)
            if not ok and state["video"]:
                cap.set(cv2.CAP_PROP_POS_FRAMES, 0)   # loop the uploaded video
        if not ok or frame is None:
            time.sleep(0.1); continue
        k = max(1, int(state["blur"])); k += (k % 2 == 0)   # force odd kernel
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        blur = cv2.GaussianBlur(gray, (k, k), 0)
        _, mask = cv2.threshold(blur, state["threshold"], 255, cv2.THRESH_BINARY)
        cnts, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        n = 0
        for c in cnts:
            if cv2.contourArea(c) >= state["min_area"]:
                n += 1
                x, y, w, h = cv2.boundingRect(c)
                cv2.rectangle(frame, (x, y), (x + w, y + h), (0, 255, 0), 2)
        state["live"] = n; state["hist"].append(n)
        avg = sum(state["hist"]) / len(state["hist"])
        cv2.putText(frame, f"Live: {n}  Avg30: {avg:.1f}", (10, 25),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
        latest["normal"] = cv2.imencode(".jpg", frame)[1].tobytes()
        latest["mask"] = cv2.imencode(".jpg", mask)[1].tobytes()
        time.sleep(0.03)

threading.Thread(target=worker, daemon=True).start()

def mjpeg(key):
    while True:
        if latest[key]:
            yield b"--frame\r\nContent-Type: image/jpeg\r\n\r\n" + latest[key] + b"\r\n"
        time.sleep(0.03)

@app.get("/")
def home():
    return FileResponse(os.path.join(BASE, "index.html"))

@app.post("/update_params")
def update_params(p: Params):
    state.update(blur=p.blur | 1, threshold=p.threshold, min_area=p.min_area)
    return {"ok": True}

@app.post("/set_source")
def set_source(s: Source):
    global cap
    with lock:
        cap.release(); cap = cv2.VideoCapture(s.source); state["video"] = False
    return {"ok": True}

@app.post("/upload_video")
async def upload_video(file: UploadFile = File(...)):
    global cap
    name = os.path.basename(file.filename).replace(" ", "_")
    path = os.path.join(UPLOAD_DIR, name)
    with open(path, "wb") as f:
        shutil.copyfileobj(file.file, f)
    with lock:
        cap.release()
        cap = cv2.VideoCapture(path)
        if not cap.isOpened():
            raise HTTPException(status_code=400, detail="OpenCV could not open this video")
        state["video"] = True
    return {"ok": True, "file": name}

@app.get("/stats")
def stats():
    avg = sum(state["hist"]) / len(state["hist"]) if state["hist"] else 0
    level = "SAFE" if avg < 5 else "MODERATE" if avg <= 20 else "CRITICAL"
    return {"live_count": state["live"], "avg_count": round(avg, 1), "danger_level": level}

@app.get("/video_feed")
def video_feed():
    return StreamingResponse(mjpeg("normal"), media_type="multipart/x-mixed-replace; boundary=frame")

@app.get("/processed_feed")
def processed_feed():
    return StreamingResponse(mjpeg("mask"), media_type="multipart/x-mixed-replace; boundary=frame")