

from datetime import datetime
from enum import Enum
from typing import List
from bidict import bidict


class Player:
    
    def __init__(self, name: str, id: str, team: 'Team'):
        self.name = name
        self.id = id
        self.team = team


class Team:

    def __init__(self, name: str):
        self.name = name
        self.players: List[Player] = []
    

class Matchup:
    
    def __init__(self, team_a: Team, team_b: Team):
        self.teams: List[Team] = [team_a, team_b]
        self.games: List[Game] = []
    
    def import_games_from_pairing_lists(self, player_games: List[List[Player]]):
        for i in range(12):
            self.games.append(Game([player_games[0][i], player_games[1][i]]))

class Game:

    class Outcome(Enum):
        WAITING_FOR_PLAYERS = "WaitingForPlayers"
        DISTRIBUTING_TERRITORIES = "DistributingTerritories"
        IN_PROGRESS = "Playing"
        FINISHED = "Finished"
        VOTED_TO_END = "voted_to_end"
        UNDEFINED = "undefined"

    def __init__(self, players, outcome=Outcome.UNDEFINED, link="") -> None:
        self.outcome: Game.Outcome = outcome
        self.winner: str = ""
        self.players: List[Player] = players
        self.link: str = link


class WarzonePlayer:

    class Outcome(Enum):
        WON = "Won"
        INVITED = "Invited"
        DECLINED = "Declined"
        SURRENDER_ACCEPTED = "SurrenderAccepted"
        VOTED_TO_END = "voted_to_end"
        UNDEFINED = "undefined"

    def __init__(self, name, id, outcome=""):
        self.name: str = name
        self.id: int = id
        self.team: str = ""

        if outcome == "":
            self.outcome = WarzonePlayer.Outcome.UNDEFINED
        else:
            self.outcome = WarzonePlayer.Outcome(outcome)


class WarzoneGame:

    def __init__(self, players, outcome=Game.Outcome.UNDEFINED, link="", start_time=datetime.now()) -> None:
        self.outcome: Game.Outcome = outcome
        self.winner: str = ""
        self.players: List[WarzonePlayer] = players
        self.link: str = link
        self.start_time: datetime = start_time

TEAM_NAME_TO_API_VALUE = bidict({
    "canada": "1",
    "quebec": "2",
    "greenland": "3",
    "iceland": "4"
})