import cv2 as cv
import numpy as np
#img = cv.imread('wallpaper.jpg')
#cv.imshow('batman',img)
#cv.waitKey(0)
vid =cv.VideoCapture(r'D:\RVCE\RVCE 1st Sem\Main EL\OpenCV\Sample_video.mp4')
while True:
    isTrue, frame= vid.read()
    frame = cv.cvtColor(frame, cv.COLOR_BGR2GRAY)
    blur = cv.GaussianBlur(frame , (5,5) , cv.BORDER_DEFAULT)
    threshold , thresh = cv.threshold(blur , 105 , 255 , cv.THRESH_BINARY)
    canny = cv.Canny(blur , 90 ,150 )
    contours , hierarchy = cv.findContours(canny , cv.RETR_LIST , cv.CHAIN_APPROX_NONE)
    #cv.imshow('video', frame)
    #cv.imshow('blur', blur)
    cv.imshow('THRESH', thresh)
    #cv.imshow('canny ', canny)
    print(len(contours))

    if cv.waitKey(20) & 0xFF==ord('g'):
        break
vid.release()
cv.destroyAllWindows()        

