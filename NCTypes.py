

from datetime import datetime
from enum import Enum
from typing import Dict, List, Tuple
from bidict import bidict

NUM_GAMES = 12

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
    
    def import_2v2_games_from_pairing_lists(self, player_games: List[Tuple[Player, Player]]):
        for i in range(6):
            self.games.append(Game([player_games[0][i], player_games[1][i]]))

class Game:

    class Outcome(Enum):
        WAITING_FOR_PLAYERS = "WaitingForPlayers"
        DISTRIBUTING_TERRITORIES = "DistributingTerritories"
        IN_PROGRESS = "Playing"
        FINISHED = "Finished"
        UNDEFINED = "undefined"

    def __init__(self, players, outcome=Outcome.UNDEFINED, link="") -> None:
        self.outcome: Game.Outcome = outcome
        self.winner: str = ""
        self.players: List[Player] = players
        self.link: str = link
    
    def __repr__(self) -> str:
        players_by_team: Dict[str, List[str]] = {}
        for player in self.players:
            players_by_team.get(player.team.name, []).append(player.name.encode())
        
        team_strings: List[str] = []
        for players in players_by_team.values():
            team_strings.append(", ".join(players))
        
        return " vs. ".join(team_strings)


class WarzonePlayer:

    class Outcome(Enum):
        WON = "Won"
        PLAYING = "Playing"
        INVITED = "Invited"
        SURRENDER_ACCEPTED = "SurrenderAccepted"
        ELIMINATED = "Eliminated"
        BOOTED = "Booted"
        ENDED_BY_VOTE = "EndedByVote"
        DECLINED = "Declined"
        REMOVED_BY_HOST = "RemovedByHost"
        UNDEFINED = "undefined"

    def __init__(self, name, id, outcome=""):
        self.name: str = name
        self.id: int = id
        self.team: str = ""
        self.score: int = 0

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
    "AUS A": "1",
    "AUS B": "2",
    "BEL": "3",
    "CAN": "4",
    "CZE": "5",
    "EAS": "6",
    "FR A": "7",
    "FR B": "8",
    "FR C": "9",
    "GB A": "10",
    "GB B": "11",
    "GB C": "12",
    "GER A": "13",
    "GER B": "14",
    "GER C": "15",
    "HEL A": "16",
    "HEL B": "17",
    "HEL C": "18",
    "HIS": "19",
    "ITA A": "20",
    "ITA B": "21",
    "ITA C": "22",
    "ITA D": "23",
    "ITA E": "24",
    "NL": "25",
    "POL A": "26",
    "POL B": "27",
    "POL C": "28",
    "SWZ": "29",
    "US A": "30",
    "US B": "31",
    "US C": "32",
    "US D": "33"
})

class TeamResult:

    def __init__(self, name) -> None:
        self.name: str = name
        self.players: List[PlayerResult] = []
        self.round_wins: float = 0
        self.round_losses: float = 0
        self.games_result: Dict[str, GameResult] = {}

    def init_score(self, round: str, opp: str, pts_for: int, pts_against: int):
        if round not in self.games_result:
            self.games_result[round] = GameResult(opp, pts_for, pts_against)

    def update_round_score(self, round: str):
        if self.games_result[round].total == NUM_GAMES:
            # round over
            if self.games_result[round].pts_for > self.games_result[round].pts_against + 1:
                # Full win
                self.round_wins += 1
            elif self.games_result[round].pts_for > self.games_result[round].pts_against:
                # Close win
                self.round_wins += 0.75
                self.round_losses += 0.25
            elif self.games_result[round].pts_for + 1 < self.games_result[round].pts_against:
                # Full loss
                self.round_losses += 0
            elif self.games_result[round].pts_for < self.games_result[round].pts_against:
                # Close loss
                self.round_wins += 0.25
                self.round_losses += 0.75
            else:
                # Draw
                self.round_wins += 0.5
                self.round_losses += 0.5
    
    def add_win(self, round: str):
        self.games_result[round].add_win()
        if self.games_result[round].total == NUM_GAMES:
            # Round over
            self.update_round_score(round)
    
    def add_loss(self, round: str):
        self.games_result[round].add_loss()
        if self.games_result[round].total == NUM_GAMES:
            # Round over
            self.update_round_score(round)

class GameResult:
    
    def __init__(self, opp: str, starting_pts_for = 0, starting_pts_against = 0) -> None:
        self.opp = opp
        self.pts_for = starting_pts_for
        self.pts_against = starting_pts_against
        self.wins = 0
        self.losses = 0
        self.total = 0
    
    def add_win(self):
        self.wins += 1
        self.pts_for += 1
        self.total += 1
    
    def add_loss(self):
        self.losses += 1
        self.pts_against += 1
        self.total += 1


class PlayerResult:
    
    def __init__(self, name, id, team) -> None:
        self.name: str = name
        self.id: int = id
        self.wins: int = 0
        self.losses: int = 0
        self.team: str = team
