import librosa

class Synthesizer:
    def __init__(self, file: str) -> object:
        
        """
        An object for manipulating sound clips.
        ---
        file, str: The location of the sound file on the host system.
        """

        self.sound_file = file

    def load_sound(self):
        """
        Loads the file into the object.
        """

        self.sound = librosa.load(self.sound_file, sr=None)
