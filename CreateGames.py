

from sheet import GoogleSheet


class CreateGames:

    def __init__(self, config):
        self.config = config
        self.sheet = GoogleSheet(config)
