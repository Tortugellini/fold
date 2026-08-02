import librosa


class Synthesizer:
    def __init__(self, sound_data: str | bytes) -> object:
        """
        An object for manipulating sound clips.
        ---
        sound_data, str | bytes: Either the directory string to a file or a bytes object.
        """

        self.sound_data = sound_data

    def load_sound(self):
        """
        Loads the file into the object.
        """

        self.sound = librosa.load(self.sound_data, sr=None)
