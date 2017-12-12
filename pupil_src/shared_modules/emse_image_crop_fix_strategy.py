from emse_image_crop_strategy import Emse_image_crop_strategy
import cv2 

class Emse_image_crop_fix_strategy(Emse_image_crop_strategy):
    """ Crop part of image with a fix pixel size"""
    
    size = 0 # Default size is 175. Can be changed after the object is constructed
    width_ratio = 1.5

    def __init__(self, size=175):
        #super().__init__()
        self.size = size
        
    def crop(self, img, gaze_x, gaze_y):
        height = self.size
        width = int(self.size * self.width_ratio)

        start_x = gaze_x - width if (gaze_x - width) > 0 else 0
        end_x = gaze_x + width if (gaze_x + width) < 1280 else 1280
        start_y = gaze_y - height if (gaze_y - height) > 0 else 0
        end_y = gaze_y + height if (gaze_y + height) < 1280 else 1280

        return {'img' : img[start_y:end_y, start_x:end_x], 'corner' : [start_x, start_y], 'size' : [2*width, 2*height]}