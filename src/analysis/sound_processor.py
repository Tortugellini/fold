from playsound3 import playsound

class Synthesizer:
    def __init__(
            self,
            file: str
        ) -> object:
        
        """
        An object for manipulating sound clips.
        """

        self.sound_file = file

    def _play_sound(self):
        """
        Internal method used to play the sound in the file.
        """

        playsound(self.sound_file, block=False)

    def play_sound(self):
        """
        Plays the sound in the file.
        """

        self._play_sound()
