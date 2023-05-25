

from enum import Enum


class Player:
    
    def __init__(self, name: str, id: str):
        self.name = name
        self.id = id

class Country:

    def __init__(self):
        pass



class GameResult:

    class Outcome(Enum):
        WAITING_FOR_PLAYERS = "WaitingForPlayers"
        DISTRIBUTING_TERRITORIES = "DistributingTerritories"
        IN_PROGRESS = "Playing"
        FINISHED = "Finished"
        VOTED_TO_END = "voted_to_end"

    def __init__(self, outcome: Outcome) -> None:
        self.outcome
        self.players
