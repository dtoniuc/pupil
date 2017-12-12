'''
(*)~---------------------------------------------------------------------------
Pupil - eye tracking platform
Copyright (C) 2012-2017  Pupil Labs

Distributed under the terms of the GNU
Lesser General Public License (LGPL v3.0).
See COPYING and COPYING.LESSER for license details.
---------------------------------------------------------------------------~(*)
'''

from plugin import Plugin
from pyglui import ui, cygl
from collections import deque
from methods import denormalize
from pyglui.cygl.utils import draw_rounded_rect, RGBA
import cv2 
import numpy as np
import logging
from timeit import default_timer as timer

from PIL import Image
import pytesseract as tes
import re

from emse_image_processor import Emse_image_processor
from emse_speech_producer import Emse_speech_producer

logger = logging.getLogger(__name__)

class Emse_numero_plugin(Plugin):
    """
    Detect text/numbers from the image frame and turn them into speech
    """

    uniqueness = "by_class"
    order = .8
    icon_chr = chr(0xe81a)
    icon_font = 'pupil_icons'

    number_regex = re.compile('[^0-9 \n]*')
    tmp_img = './tmp/tmp_img.png'
    
    rotate_flag = False
    fixation_flag = False
    only_numbers_flag = False

    image_processor = None
    speech_producer = None
    
    def __init__(self, g_pool, rotate_flag = False, only_numbers_flag = False):
        super(Emse_numero_plugin, self).__init__(g_pool)
        self.last_fixation_id = 0
        self.fixation_flag = False
        
        self.menu = None

        self.image_processor = Emse_image_processor()
        self.speech_producer = Emse_speech_producer()
        self.result = None

    def init_ui(self):
        self.add_menu()
        self.menu.label = 'Numero plugin'
        self.menu.append(ui.Info_Text('This plugin reads text from the camera and outputs it as an audio.'))
        self.menu.append(ui.Selector('selected_crop_strategy', self.image_processor,
                                     selection=self.image_processor.crop_strategy_list,
                                     labels=['Fix cropping', 'Contour cropping'],
                                     label="Crop method"))
        
        self.menu.append(ui.Slider('size', self.image_processor.crop_strategy_list[0], label='[Fix crop] Size in pixels', min=50, max=200, step=10))
        self.menu.append(ui.Slider('dilation', self.image_processor.crop_strategy_list[1], label='[Contour crop] Dilation', min=0, max=30, step=1))
        
        self.menu.append(ui.Switch('rotate_flag', self , label='Rotation'))
        self.menu.append(ui.Switch('only_numbers_flag', self , label='Only numbers'))

    def deinit_ui(self):
        self.remove_menu()

    def recent_events(self, events):
        if 'frame' in events:
            frame = events['frame']
            gaze = events['gaze_positions']
            fixations = events['fixations']

            if gaze and fixations and fixations[-1]['id'] != self.last_fixation_id:
                
                #start = timer()
                #update last fixation
                self.last_fixation_id = fixations[-1]['id']

                #get the gaze coordinates in the world image
                gaze_x, gaze_y = self.get_gaze_coordinates(frame, fixations[-1]['norm_pos'])

                preprocessed_img = self.image_processor.binarize(frame.img)
                #extract sub-image 
                self.result = self.image_processor.crop(preprocessed_img, gaze_x, gaze_y)

                #rotate the image if the rotation flag is active
                subimage = self.result['img']
                if self.rotate_flag == True:
                    subimage = self.image_processor.rotate(subimage)
                #print the image to be used by the ocr
                cv2.imwrite(self.tmp_img, subimage)
                
                #ocr
                start = timer()
                output = self.read_text_from_image(self.number_regex, self.tmp_img)
                end = timer()

                #text to voice
                if output.strip() != '':
                    self.speech_producer.say(output)

                #end = timer()
                print('--------------------------------------------------' + str(end - start))

            if fixations:
                self.fixation_flag = True
            else:
                self.fixation_flag = False

    def get_init_dict(self):
        return {}

    def gl_display(self):
        if self.result != None and self.fixation_flag == True:
            draw_rounded_rect(self.result['corner'], self.result['size'], 0, color=RGBA(.200, .200, .200, 0.4))

    def read_text_from_image(self, regex, tmp_img):
        results = tes.image_to_string(Image.open(tmp_img))
        if self.only_numbers_flag == True:
            return regex.sub('',results)
        return results 

    def get_gaze_coordinates(self, frame, normal_position):
        fs = [frame.width, frame.height]
        gaze_x, gaze_y = denormalize(normal_position, fs, flip_y=True)
        return int(gaze_x), int(gaze_y)