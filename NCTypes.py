

from enum import Enum
from typing import List


class Player:
    
    def __init__(self, name: str, id: str, team: 'Team'):
        self.name = name
        self.id = id
        self.team = team


class Team:

    def __init__(self, name: str, players = []):
        self.name = name
        self.players: List[Player] = players
    

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
        self.players: List[Player] = players
        self.link: str = link
