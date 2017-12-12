from emse_image_crop_strategy import Emse_image_crop_strategy
import cv2 
import numpy as np

class Emse_image_crop_contour_strategy(Emse_image_crop_strategy):
    """ Identify the contours in the image and then crop part the image on the contour
    which contain the gazing position. If gazing position is outside of any countour the
    whole image is returned"""
    
    dilation = 0

    def __init__(self, dilation=10):
        #super().__init__()
        self.dilation = dilation
        
    def crop(self, img, gaze_x, gaze_y):
        #cv2.imwrite("./tmp/thresh.png", img)
        kernel = np.ones((5,5),np.uint8)
        #erosion = cv2.erode(rthresh,kernel,iterations = 2)
        dilated_img = cv2.dilate(img, kernel, iterations = self.dilation)
        #cv2.imwrite("./tmp/erosion.png", dilation)

        contours = cv2.findContours(dilated_img, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE) [1]
        
        for contour in contours:
            [start_x,start_y,width,height] = cv2.boundingRect(contour)
            end_x = start_x + width
            end_y = start_y + height 
            if gaze_x >= start_x and gaze_x <= end_x and gaze_y >= start_y and gaze_y <= end_y:
                return {'img' : img[start_y:end_y, start_x:end_x], 'corner' : [start_x, start_y], 'size' : [width, height]}
        
        return {'img' : img, 'corner' : [0, 0], 'size' : img.shape[:2]}