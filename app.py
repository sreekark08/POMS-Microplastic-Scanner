import cv2
import numpy as np
import streamlit as st
import datetime
import tempfile

# --- WEB APP SETUP ---
st.set_page_config(page_title="POMS Dashboard", layout="wide")
st.title("🔬 POMS: Microplastic Contamination Scanner")

# --- SESSION STATE ---
if 'particle_history' not in st.session_state:
    st.session_state['particle_history'] = []

# --- SIDEBAR: VIDEO SOURCE SELECTION ---
st.sidebar.header("1. Data Source")
source_option = st.sidebar.radio("Select Input Source:", ("Live Camera", "Upload Video File"))

video_input = 0 # Default to webcam (0)
uploaded_file = None

if source_option == "Upload Video File":
    uploaded_file = st.sidebar.file_uploader("Upload MP4/AVI file", type=['mp4', 'avi', 'mov'])
    if uploaded_file is not None:
        # OpenCV needs a file path to read videos, so we save the uploaded file temporarily
        tfile = tempfile.NamedTemporaryFile(delete=False)
        tfile.write(uploaded_file.read())
        video_input = tfile.name

# --- SIDEBAR: CONTROLS ---
st.sidebar.header("2. Optical Calibration")
threshold_value = st.sidebar.slider("Binary Threshold", min_value=0, max_value=255, value=105)
min_area = st.sidebar.slider("Minimum Particle Size", min_value=10, max_value=200, value=50)

st.sidebar.markdown("---")
run_scanner = st.sidebar.checkbox("🟢 Run Scanner", value=False)
download_placeholder = st.sidebar.empty()

# --- REPORT GENERATOR FUNCTION ---
def generate_report(avg_count):
    date_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    if avg_count < 5:
        level = "SAFE (Low Contamination)"
        solutions = "- Maintain current water source.\n- No additional aggressive filtration needed at this time."
    elif avg_count <= 20:
        level = "MODERATE HAZARD"
        solutions = "- Install a 1-micron mechanical sediment filter.\n- Utilize activated carbon block filters."
    else:
        level = "CRITICAL HAZARD"
        solutions = "- IMMEDIATE ACTION: Do not consume.\n- Implement a Reverse Osmosis (RO) membrane system.\n- Use sub-micron (0.1 µm) glass fiber filtration."

    report = f"""======================================
POMS WATER QUALITY DIAGNOSTIC REPORT
======================================
Timestamp: {date_str}

[ SCAN RESULTS ]
Average Microplastic Count: {avg_count} particles
Danger Level: {level}

[ RECOMMENDED SOLUTIONS ]
{solutions}
======================================"""
    return report

# --- MAIN LAYOUT ---
col1, col2 = st.columns([2, 1])
st_frame = col1.empty()
status_panel = col2.empty()

# --- OPENCV VIDEO LOOP ---
# Only run if 'Run Scanner' is checked AND (we are on Live OR we uploaded a file)
if run_scanner and (source_option == "Live Camera" or uploaded_file is not None):
    cap = cv2.VideoCapture(video_input)

    while cap.isOpened() and run_scanner:
        ret, frame = cap.read()
        if not ret:
            st.info("End of video stream.")
            break

        # 1. Image Processing
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        blur = cv2.GaussianBlur(gray, (3, 3), 0)
        _, thresh = cv2.threshold(blur, threshold_value, 255, cv2.THRESH_BINARY)
        contours, _ = cv2.findContours(thresh, cv2.RETR_LIST, cv2.CHAIN_APPROX_NONE)

        # 2. Particle Detection
        valid_particles = 0
        for cnt in contours:
            if cv2.contourArea(cnt) > min_area:
                valid_particles += 1
                x, y, w, h = cv2.boundingRect(cnt)
                cv2.rectangle(frame, (x, y), (x + w, y + h), (0, 255, 0), 2)

        # 3. Calculate Moving Average
        st.session_state['particle_history'].append(valid_particles)
        if len(st.session_state['particle_history']) > 30:
            st.session_state['particle_history'].pop(0)
        
        if len(st.session_state['particle_history']) > 0:
            avg_particles = int(sum(st.session_state['particle_history']) / len(st.session_state['particle_history']))
        else:
            avg_particles = 0

        # 4. AR Heads-Up Display (HUD)
        overlay = frame.copy()
        cv2.rectangle(overlay, (10, 10), (320, 140), (0, 0, 0), -1)
        cv2.addWeighted(overlay, 0.6, frame, 0.4, 0, frame)
        
        cv2.putText(frame, "POMS OPTICAL SCANNER", (25, 40), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
        cv2.putText(frame, f"LIVE COUNT: {valid_particles}", (25, 75), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 2)
        cv2.putText(frame, f"AVG (30f): {avg_particles}", (25, 110), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 0), 2)

        h_img, w_img, _ = frame.shape
        
        # 5. Dynamic Alerts
        if avg_particles > 20:
            cv2.rectangle(frame, (0, 0), (w_img, h_img), (0, 0, 255), 6)
            status_panel.error(f"🚨 CRITICAL HAZARD: {avg_particles} Avg Contaminants Detected! RO Filtration Required.")
        elif avg_particles > 5:
            cv2.rectangle(frame, (0, 0), (w_img, h_img), (0, 165, 255), 6)
            status_panel.warning(f"⚠️ MODERATE HAZARD: {avg_particles} Avg Contaminants. Carbon block filter recommended.")
        else:
            status_panel.success(f"✅ STATUS: Safe. {avg_particles} Avg Contaminants. Water clarity maintained.")

        # 6. Render Frame
        st_frame.image(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB), channels="RGB")

    cap.release()

elif run_scanner and source_option == "Upload Video File" and uploaded_file is None:
    st.warning("Please upload a video file first before running the scanner.")

# --- GENERATE REPORT OUTSIDE THE LOOP ---
if len(st.session_state['particle_history']) > 0:
    final_avg = int(sum(st.session_state['particle_history']) / len(st.session_state['particle_history']))
    report_text = generate_report(final_avg)
    
    download_placeholder.download_button(
        label="📥 Download Final Diagnostic Report",
        data=report_text,
        file_name=f"POMS_Report_{datetime.datetime.now().strftime('%Y%m%d_%H%M')}.txt",
        mime="text/plain"
    )