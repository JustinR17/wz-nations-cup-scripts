

from datetime import datetime
from enum import Enum
from typing import Dict, List, Tuple
from bidict import bidict

NUM_GAMES = 12

class Player:
    
    def __init__(self, name: str, id: str, team: 'Team'):
        self.name = name
        self.id = str(id)
        self.team = team
    
    def __lt__(self, other: 'Player'):
        return self.id < other.id if self.team.name == other.team.name else self.team.name > other.team.name
    
    def __repr__(self) -> str:
        return f'{self.name} ({self.id})'


class Team:

    def __init__(self, name: str):
        self.name = name
        self.players: List[Player] = []
    
    def __lt__(self, other: 'Team'):
        return self.name > other.name
    

class Matchup:
    
    def __init__(self, team_a: Team, team_b: Team):
        self.teams: List[Team] = sorted([team_a, team_b])
        self.games: List[Game] = []
    
    def import_games_from_pairing_lists(self, player_games: List[List[Player]]):
        for i in range(12):
            self.games.append(Game([player_games[0][i], player_games[1][i]]))
    
    def import_2v2_games_from_pairing_lists(self, player_games: List[List[Tuple[Player, Player]]]):
        for i in range(6):
            # Each game contains 2 players per team... destructure so game holds 4 players
            print(player_games[0][i])
            print(player_games[1][i])
            self.games.append(Game([*player_games[0][i], *player_games[1][i]]))
            print()

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
        self.players: List[Player] = sorted(players) # sort the players for the case of 2v2s (to match team games in sheet properly)
        self.link: str = link
    
    def __repr__(self) -> str:
        players_by_team: Dict[str, List[str]] = {}
        for player in self.players:
            players_by_team.setdefault(player.team.name, []).append(player.name)
        
        team_strings: List[str] = []
        for team, players in players_by_team.items():
            team_strings.append(f"({team}) " + ", ".join(players))
        
        return " vs. ".join(team_strings)

    def get_player_names_by_team(self):
        players_by_team: Dict[str, List[str]] = {}
        for player in self.players:
            players_by_team.setdefault(player.team.name, []).append(player.name)
        return players_by_team 

    def get_players_by_team(self):
        players_by_team: Dict[str, List[str]] = {}
        for player in self.players:
            players_by_team.get(player.team.name, []).append(player)
        
        # Sanity check to ensure proper ordering of players. Should not be needed since order is preserved
        for team_name, players in players_by_team.items():
            players_by_team[team_name] = sorted(players)
        return players_by_team 


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

    def __init__(self, name, id, outcome="", team=""):
        self.name: str = name
        self.id: int = id
        self.team: str = team
        self.score: int = 0

        if outcome == "":
            self.outcome = WarzonePlayer.Outcome.UNDEFINED
        else:
            self.outcome = WarzonePlayer.Outcome(outcome)
    
    def __repr__(self) -> str:
        return f"**{self.team}** {self.name} ({self.id})"

    def get_player_state_str(self) -> str:
        return f"{self.name.encode()} {self.outcome}"

    def __lt__(self, other: 'WarzonePlayer'):
        return self.id < other.id if self.team == other.team \
            else self.team > other.team


class WarzoneGame:

    def __init__(self, players, outcome=Game.Outcome.UNDEFINED, link="", start_time=datetime.now(), round=0) -> None:
        self.outcome: Game.Outcome = outcome
        self.winner: List[int] = []
        self.players: List[WarzonePlayer] = players
        self.link: str = link
        self.start_time: datetime = start_time
        self.round: int = round
    
    def __repr__(self) -> str:
        output_str = " vs ".join([str(player) for player in sorted(self.players)])
        output_str += f"\n\tWinner: {self.winner}"
        output_str += f"\n\tStart time: {self.start_time}"
        output_str += f"\n\tOutcome: {self.outcome}"
        output_str += f"\n\tRound: {self.round}"
        output_str += f"\n\tLink: {self.link}"
        return output_str

TEAM_NAME_TO_API_VALUE = bidict({
    "ANZ A": "1",
    "ANZ B": "2",
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
    "SUI": "29",
    "SWZ": "34", # In case marcus does anything weird
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
        if round in self.games_result:
            self.games_result.pop(round)
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
                self.round_losses += 1
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
