
import talkey
import _thread as thread
import threading

class Emse_speech_producer:
    """ A singelton class that produces speech based on the text param passed to the say() method. """
    
    __singleton = None
    __lock = threading.Lock()
    __tts = talkey.Talkey()
    
    def __new__(cls, *args, **kwargs):  
        if not cls.__singleton:  
            cls.__singleton =  object.__new__(Emse_speech_producer)  
        return cls.__singleton  

    def say(self, text):
        """ Launches a new thread to output the speech without blocking the excution of the current thread"""
        #Run a separate thread to produce the speech
        thread.start_new_thread(self.thread_say, (text,)) 
        
    def thread_say(self, text):
        """ Produce the speech output with the insurance that a single thread is producing speech - Lock - """
        #Try to Acquire the lock
        if self.__lock.acquire(blocking=False):
            self.__tts.say(text)
            self.__lock.release()