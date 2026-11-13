import cv2 as cv

img = cv.imread('wallpaper.jpg')
cv.imshow('wallpaper' , img)
cv.waitKey(0)