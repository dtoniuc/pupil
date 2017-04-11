'''
(*)~---------------------------------------------------------------------------
Pupil - eye tracking platform
Copyright (C) 2012-2017  Pupil Labs

Distributed under the terms of the GNU
Lesser General Public License (LGPL v3.0).
See COPYING and COPYING.LESSER for license details.
---------------------------------------------------------------------------~(*)
'''

import sys
import os
import platform
import zmq
import zmq_tools
import numpy as np
from plugin import Plugin
from pyglui import ui
from time import sleep
from threading import Thread
from player_methods import correlate_data
if platform.system() in ('Darwin', 'Linux'):
    from multiprocessing import get_context
    mp = get_context('forkserver')
    Value = mp.Value
    Process = mp.Process
else:
    import multiprocessing as mp
    from multiprocessing import Value, Process

from ctypes import c_double, c_bool
if 'profiled' in sys.argv:
    from eye import eye_profiled as eye
else:
    from eye import eye

import logging
logger = logging.getLogger(__name__)


class Offline_Pupil_Detection(Plugin):
    """docstring for Offline_Pupil_Detection"""
    def __init__(self, g_pool):
        super().__init__(g_pool)

        self.original_pupil_pos = self.g_pool.pupil_data
        self.original_pupil_pos_by_frame = self.g_pool.pupil_positions_by_frame

        self.eye_processes = [None, None]
        self.eye_timestamps = [None, None]
        self.detection_progress = {'0': 0., '1': 0.}
        self.pupil_positions = []
        self.detection_finished_flag = False

        # Pupil Offline Detection
        timebase = Value(c_double, 0)
        self.eyes_are_alive = Value(c_bool, 0), Value(c_bool, 0)

        logger.info('Starting eye process communication channel...')
        self.ipc_pub_url, self.ipc_sub_url, self.ipc_push_url = self.initialize_ipc()
        sleep(0.2)

        self.data_sub = zmq_tools.Msg_Receiver(self.zmq_ctx, self.ipc_sub_url, topics=('pupil.',))
        self.eye_control = zmq_tools.Msg_Dispatcher(self.zmq_ctx, self.ipc_push_url)

        for eye_id in (0, 1):
            eye_vid = os.path.join(self.g_pool.rec_dir, 'eye{}.mp4'.format(eye_id))
            try:
                timestamps_path = os.path.join(self.g_pool.rec_dir,
                                               'eye{}_timestamps.npy'.format(eye_id))
                self.eye_timestamps[eye_id] = list(np.load(timestamps_path))
                self.detection_progress[str(eye_id)] = 0.
                overwrite_cap_settings = 'File_Source', {
                    'source_path': eye_vid,
                    'timestamps': self.eye_timestamps[eye_id],
                    'timed_playback': False
                }
                eye_p = Process(target=eye, name='eye{}'.format(eye_id),
                                args=(timebase, self.eyes_are_alive[eye_id],
                                      self.ipc_pub_url, self.ipc_sub_url,
                                      self.ipc_push_url, self.g_pool.user_dir,
                                      self.g_pool.version, eye_id,
                                      overwrite_cap_settings))
                eye_p.start()
                self.eye_processes[eye_id] = eye_p
            except IOError:
                continue

        if not self.eye_processes[0] and not self.eye_processes[1]:
            logger.error('No eye recordings forund. Unloading plugin...')
            self.alive = False

    def recent_events(self, events):
        while self.data_sub.new_data:
            topic, payload = self.data_sub.recv()
            self.pupil_positions.append(payload)
            self.update_progress(payload)
        if not self.detection_finished_flag:
            eye0_finished = self.detection_progress['0'] == 1. if self.eye_processes[0] is not None else True
            eye1_finished = self.detection_progress['1'] == 1. if self.eye_processes[1] is not None else True
            if eye0_finished and eye1_finished:
                self.detection_finished_flag = True
                self.g_pool.pupil_data = self.pupil_positions
                self.g_pool.pupil_positions_by_frame = correlate_data(self.pupil_positions, self.g_pool.timestamps)
                self.notify_all({'subject': 'pupil_positions_changed'})
                logger.debug('pupil positions changed')

        if not self.eyes_are_alive[0].value and not self.eyes_are_alive[1].value:
            self.alive = False  # close the plugin if the eye windows were closed

    def update_progress(self, pupil_position):
        eye_id = pupil_position['id']
        timestamps = self.eye_timestamps[eye_id]
        cur_ts = pupil_position['timestamp']
        min_ts = timestamps[0]
        max_ts = timestamps[-1]
        self.detection_progress[str(eye_id)] = 100 * (cur_ts - min_ts) / (max_ts - min_ts)

    def cleanup(self):
        self.eye_control.notify({'subject': 'eye_process.should_stop', 'eye_id': 0})
        self.eye_control.notify({'subject': 'eye_process.should_stop', 'eye_id': 1})
        for proc in self.eye_processes:
            if proc:
                proc.join()
        # close sockets before context is terminated
        del self.data_sub
        del self.eye_control
        self.zmq_ctx.term()
        self.deinit_gui()

        self.g_pool.pupil_data = self.original_pupil_pos
        self.g_pool.pupil_positions_by_frame = self.original_pupil_pos_by_frame
        self.notify_all({'subject': 'pupil_positions_changed'})
        logger.debug('pupil positions changed')

    def redetect(self):
        del self.pupil_positions[:]  # delete previously detected pupil positions
        self.detection_finished_flag = False
        self.eye_control.notify({'subject': 'file_source.restart',
                                 'source_path': os.path.join(self.g_pool.rec_dir, 'eye0.mp4')})
        self.eye_control.notify({'subject': 'file_source.restart',
                                 'source_path': os.path.join(self.g_pool.rec_dir, 'eye1.mp4')})

    def initialize_ipc(self):
        self.zmq_ctx = zmq.Context()

        # Let the OS choose the IP and PORT
        ipc_pub_url = 'tcp://*:*'
        ipc_sub_url = 'tcp://*:*'
        ipc_push_url = 'tcp://*:*'

        # Binding IPC Backbone Sockets to URLs.
        # They are used in the threads started below.
        # Using them in the main thread is not allowed.
        xsub_socket = self.zmq_ctx.socket(zmq.XSUB)
        xsub_socket.bind(ipc_pub_url)
        ipc_pub_url = xsub_socket.last_endpoint.decode('utf8').replace("0.0.0.0", "127.0.0.1")

        xpub_socket = self.zmq_ctx.socket(zmq.XPUB)
        xpub_socket.bind(ipc_sub_url)
        ipc_sub_url = xpub_socket.last_endpoint.decode('utf8').replace("0.0.0.0", "127.0.0.1")

        pull_socket = self.zmq_ctx.socket(zmq.PULL)
        pull_socket.bind(ipc_push_url)
        ipc_push_url = pull_socket.last_endpoint.decode('utf8').replace("0.0.0.0", "127.0.0.1")

        def catchTerminatedContext(function):
            def wrapped_func(*args, **kwargs):
                try:
                    function(*args, **kwargs)
                except zmq.error.ContextTerminated as err:
                    pass
            return wrapped_func

        # Reliable msg dispatch to the IPC via push bridge.
        def pull_pub(ipc_pub_url, pull):
            ctx = zmq.Context.instance()
            pub = ctx.socket(zmq.PUB)
            pub.connect(ipc_pub_url)

            while True:
                m = pull.recv_multipart()
                pub.send_multipart(m)

        # Starting communication threads:
        # A ZMQ Proxy Device serves as our IPC Backbone
        self.ipc_backbone_thread = Thread(target=catchTerminatedContext(zmq.proxy), args=(xsub_socket, xpub_socket))
        self.ipc_backbone_thread.setDaemon(True)
        self.ipc_backbone_thread.start()

        self.pull_pub = Thread(target=catchTerminatedContext(pull_pub), args=(ipc_pub_url, pull_socket))
        self.pull_pub.setDaemon(True)
        self.pull_pub.start()

        del xsub_socket, xpub_socket, pull_socket
        return ipc_pub_url, ipc_sub_url, ipc_push_url

    def init_gui(self):
        def close():
            self.alive = False
        self.menu = ui.Scrolling_Menu("Offline Pupil Detection", size=(200,300))
        self.g_pool.gui.append(self.menu)
        self.menu.append(ui.Button('Close', close))

        for eye_id in (0, 1):
            if self.eye_timestamps[eye_id]:
                progress_slider = ui.Slider(str(eye_id), self.detection_progress,
                                            label='Progress Eye {}'.format(eye_id),
                                            min=0.0, max=1., step=0.01)
                progress_slider.display_format = '{:3.0f} %'
                progress_slider.read_only = True
                self.menu.append(progress_slider)

        self.menu.append(ui.Button('Redetect', self.redetect))

    def deinit_gui(self):
        if hasattr(self, 'menu'):
            self.g_pool.gui.remove(self.menu)
            self.menu = None

    def get_init_dict(self):
        return {}