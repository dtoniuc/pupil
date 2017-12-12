from emse_image_crop_fix_strategy import Emse_image_crop_fix_strategy
from emse_image_crop_contour_strategy import Emse_image_crop_contour_strategy
from emse_image_crop_strategy import Emse_image_crop_strategy
import cv2 
import numpy as np

class Emse_image_processor:

    crop_strategy_list = []
    selected_crop_strategy = None

    def __init__(self):
        self.crop_strategy_list = [Emse_image_crop_fix_strategy(), Emse_image_crop_contour_strategy()]
        self.selected_crop_strategy = self.crop_strategy_list[0]

    def binarize(self, image):
        # convert the image to grayscale and flip the foreground and background to ensure foreground is 
        # now "white" and the background is "black"
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        gray = cv2.bitwise_not(gray)

        # threshold the image, setting all foreground pixels to 255 and all background pixels to 0
        thresh = cv2.threshold(gray, 0, 255,cv2.THRESH_BINARY | cv2.THRESH_OTSU)[1]

        return thresh

    def crop(self, img, gaze_x, gaze_y):
        return self.selected_crop_strategy.crop(img, gaze_x, gaze_y)

    def rotate(self, image):
        # source: https://www.pyimagesearch.com/2017/02/20/text-skew-correction-opencv-python/

        # grab the (x, y) coordinates of all pixel values that are greater than zero, then use these coordinates to
        # compute a rotated bounding box that contains all coordinates
        coords = np.column_stack(np.where(image > 0))
        angle = cv2.minAreaRect(coords)[-1]
    
        # the `cv2.minAreaRect` function returns values in the range [-90, 0); as the rectangle rotates clockwise the
        # returned angle trends to 0 -- in this special case we need to add 90 degrees to the angle
        if angle < -45:
            angle = -(90 + angle)
    
        # otherwise, just take the inverse of the angle to make it positive
        else:
            angle = -angle

        # rotate the image to deskew it
        (h, w) = image.shape[:2]
        center = (w // 2, h // 2)
        M = cv2.getRotationMatrix2D(center, angle, 1.0)
        rotated = cv2.warpAffine(image, M, (w, h),flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE)

        return rotated