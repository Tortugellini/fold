import numpy as np
import pyaudio
import time

from PyQt6 import QtCore

from constants import SAMPLE_RATE, CHUNK


class AudioPlayer(QtCore.QObject):
    """Plays the sound collected by the StreamHandler."""

    def __init__(self, mode: str, sound_data: np.array):
        super().__init__()
        self.mode = mode
        self.sound_data = sound_data
        self.stop = False

    def _callback(
        self, in_data: np.array, frame_count: int, time_info: dict, status_flags: int
    ):
        """
        Internal function used to pass data to pyaudio's stream.
        ---
        Parameters:
            in_data, np.array: Data from the 'RollingBuffer.'
            fram_count, int: The number of frames to play.
            time_info, dict:
            status_flags, int: An integer value that corresponds to values of an Enum in PortAudio.
                         The flag used should have the value of 0 which indicates to continue
                         the stream.
        ---
        Returns: A tuple containing the new data for the stream and a required flag that indicates to
                 continue streaming the sound.
        """

        if np.all(self.sound_data == in_data):
            return (self.sound_data, pyaudio.paContinue)

    def play_sounds(self):
        """
        Plays the data in sound_data. Since this is a 'RollingBuffer' object, new data should be
        handled in a FIFO manner.
        """

        # Instantiating so a stream can be created to play the sound.
        p = pyaudio.PyAudio()

        # Opening the stream.
        stream = p.open(
            format=pyaudio.paInt16,
            channels=1,
            rate=SAMPLE_RATE,
            output=False,  # For now. Will change to 'True' in future for recording functionality.
            input=True,
            stream_callback=self._callback,
        )

        # Playing the sound until told to stop.
        while not self.stop:
            time.sleep(0.1)

        # Closing the stream and PortAudio system resources.
        stream.close()
        p.terminate()
