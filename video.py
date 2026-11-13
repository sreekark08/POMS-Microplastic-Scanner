import cv2 as cv

def rescaleFrame(frame , scale=0.75):
    width = int(frame.shape[1]*scale)
    height= int(frame.shape[0]*scale)

    dimension = (width,height)

    return cv.resize(frame, dimension, interpolation=cv.INTER_AREA)

capture = cv.VideoCapture(0)

while True:
    isTrue, frame = capture.read()
    frame_resized = rescaleFrame(frame)
    
    # If the video has ended or failed to load, break out of the loop
    if not isTrue:
        break
        
    cv.imshow('Video', frame)
    cv.imshow('Video Resized', frame_resized)
    
    if cv.waitKey(20) & 0xFF == ord('d'):
        break

capture.release()
cv.destroyAllWindows()