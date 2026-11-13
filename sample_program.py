import cv2 as cv
import numpy as np

# Change 0 to your video file path if you are using a saved MP4 (e.g., "sample.mp4")
vid = cv.VideoCapture(r'D:\RVCE\RVCE 1st Sem\Main EL\OpenCV\Sample_video.mp4')

while vid.isOpened():
    ret, frame = vid.read()
    
    # If the video ends or cannot be read, break the loop
    if not ret:
        print("End of video stream or cannot fetch the frame.")
        break

    # 1. Convert to Grayscale
    gray = cv.cvtColor(frame, cv.COLOR_BGR2GRAY)

    # 2. Apply Gaussian Blur
    blur = cv.GaussianBlur(gray, (3, 3), cv.BORDER_DEFAULT)

    # 3. Apply Binary Thresholding (Adjust '105' if your particles are too bright/dark)
    threshold_value, thresh = cv.threshold(blur, 105, 255, cv.THRESH_BINARY)

    # 4. Find Contours
    contours, hierarchy = cv.findContours(thresh, cv.RETR_LIST, cv.CHAIN_APPROX_NONE)

    # 5. Filter and Draw Bounding Boxes
    valid_particles = 0

    for contour in contours:
        area = cv.contourArea(contour)

        # Filter out noise smaller than 50 pixels
        if area > 40:
            valid_particles += 1
            
            # Calculate the bounding box
            x, y, w, h = cv.boundingRect(contour)

            # Draw a green rectangle on the original color frame
            cv.rectangle(frame, (x, y), (x + w, y + h), (0, 255, 0), 2)
            
            # Label the particle
            cv.putText(frame, "Microplastic", (x, y - 5), cv.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1)

    # Print live count to the VS Code terminal
    print(f"Live Count: {valid_particles} particles detected")
    # --- AR HEADS-UP DISPLAY (HUD) ---

    # 1. Create a translucent dark data panel on the top-left
    overlay = frame.copy()
    cv.rectangle(overlay, (10, 10), (320, 140), (0, 0, 0), -1)
    # Blend it with the original frame (60% opacity)
    cv.addWeighted(overlay, 0.6, frame, 0.4, 0, frame)

    # 2. Add System Text to the Panel
    cv.putText(frame, "POMS OPTICAL SCANNER", (25, 40), cv.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
    cv.putText(frame, f"TARGETS LOCKED: {valid_particles}", (25, 75), cv.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 2)

    # 3. Dynamic Hazard Warning Logic
    if valid_particles > 5:
        # Threat level high: Red text and flash a red border around the whole screen
        cv.putText(frame, "STATUS: HAZARD DETECTED", (25, 110), cv.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 255), 2)
        cv.rectangle(frame, (0, 0), (frame.shape[1], frame.shape[0]), (0, 0, 255), 6)
    else:
        # Safe baseline: Green text
        cv.putText(frame, "STATUS: CLEAR", (25, 110), cv.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)

    # 4. Draw a Center Targeting Crosshair
    height, width, _ = frame.shape
    cx, cy = int(width / 2), int(height / 2)
    cv.line(frame, (cx - 20, cy), (cx + 20, cy), (255, 255, 255), 1)
    cv.line(frame, (cx, cy - 20), (cx, cy + 20), (255, 255, 255), 1)
    cv.circle(frame, (cx, cy), 15, (255, 255, 255), 1)

    # 6. Display the Windows
    cv.imshow('POMS Final Output', frame)
    cv.imshow('THRESH Debug', thresh) # Keep this to see what the computer "sees"

    # Press 'q' to safely exit the video loop
    if cv.waitKey(20) & 0xFF == ord('q'):
        break

# Cleanup
vid.release()
cv.destroyAllWindows()