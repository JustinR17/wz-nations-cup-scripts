import json
import random
from typing import Dict, List, Tuple

import jsonpickle
from NCTypes import (
    TEAM_NAME_TO_API_VALUE,
    Game,
    GameResult,
    PlayerResult,
    TeamResult,
    WarzoneGame,
    WarzonePlayer,
)
from api import API
from sheet import GoogleSheet
import re

from utils import log_exception, log_message


class ValidateResults:
    def __init__(self, config):
        self.config = config
        self.sheet = GoogleSheet(config)
        self.api = API(config)

    def run(self):
        """
        Reads the google sheets games and updates finished games. Newly finished games are stored in a buffer file for the discord bot to read
        """
        try:
            log_message("Running ParseGames", "ParseGames.run")
            self.validate_scores()
            self.write_player_standings()
            self.write_team_standings()
        except Exception as e:
            log_exception(e)

    def validate_scores(self):
        """
        Checks all games and updates the team & player results in the `Validate_` prefix tabs. This is to correct any mistakes in ParseGames.

        Returns a dictionary of lists (tab name -> List[Games])
        """

        team_standings: Dict[str, TeamResult] = {}
        player_standings: Dict[str, GameResult] = {}
        for tab in self.get_game_tabs():
            is_2v2 = "2v2" in tab
            tab_rows = self.sheet.get_rows(f"{tab}!A1:{'K' if is_2v2 else'G'}300")
            log_message(f"Checking games in game log tab '{tab}'", "update_new_games")

            team_a, team_b = "", ""
            for i, row in enumerate(tab_rows):
                if i == 0:
                    continue
                if not row:
                    # Finished the previous matchup
                    team_a, team_b = "", ""
                else:
                    if not team_a and not team_b:
                        # New teams to add
                        team_a, team_b = row[0].strip(), row[5 if is_2v2 else 3].strip()
                        team_standings.setdefault(team_a, TeamResult(team_a))
                        team_standings[team_a].games_result[tab[0:2]] = GameResult(team_b, int(row[2 if is_2v2 else 1]), int(row[7 if is_2v2 else 4]))
                        team_standings.setdefault(team_b, TeamResult(team_b))
                        team_standings[team_b].games_result[tab[0:2]] = GameResult(team_a, int(row[7 if is_2v2 else 4]), int(row[2 if is_2v2 else 1]))
                        if team_a:
                            log_message(
                                f"Checking games for {tab} - {team_a} vs {team_b}",
                                "update_new_games",
                            )
                    else:
                        # Game to check
                        # 2v2 requires more advanced logic that is separated out for now
                        try:
                            game = self.api.check_game(
                                self.convert_wz_game_link_to_id(
                                    row[9 if is_2v2 else 5].strip()
                                )
                            )
                        except:
                            # if the game is deleted, this will throw an exception
                            if is_2v2:
                                players = [
                                    WarzonePlayer(
                                        row[0],
                                        row[1],
                                        "Won"
                                        if row[4] == "defeats"
                                        else "SurrenderAccepted",
                                        team_a,
                                    ),
                                    WarzonePlayer(
                                        row[2],
                                        row[3],
                                        "Won"
                                        if row[4] == "defeats"
                                        else "SurrenderAccepted",
                                        team_a,
                                    ),
                                    WarzonePlayer(
                                        row[5],
                                        row[6],
                                        "Won"
                                        if row[4] == "loses to"
                                        else "SurrenderAccepted",
                                        team_b,
                                    ),
                                    WarzonePlayer(
                                        row[7],
                                        row[8],
                                        "Won"
                                        if row[4] == "loses to"
                                        else "SurrenderAccepted",
                                        team_b,
                                    ),
                                ]
                            else:
                                players = [
                                    WarzonePlayer(
                                        row[0],
                                        row[1],
                                        "Won"
                                        if row[2] == "defeats"
                                        else "SurrenderAccepted",
                                        team_a,
                                    ),
                                    WarzonePlayer(
                                        row[3],
                                        row[4],
                                        "Won"
                                        if row[2] == "loses to"
                                        else "SurrenderAccepted",
                                        team_b,
                                    ),
                                ]
                            game = WarzoneGame(
                                players,
                                Game.Outcome.FINISHED,
                                row[9] if is_2v2 else row[5],
                            )

                        if is_2v2:
                            # Separate workflow for 2v2 games that will be extended to any XvX games
                            print(f"Running the 2v2 workflow")
                            self.score_2v2_game(
                                game,
                                (team_a, team_b),
                                tab,
                                team_standings,
                                player_standings,
                            )
                            continue
                        print(f"Running the 1v1 workflow")

                        if game.players[0].id != row[1].strip():
                            game.players.reverse()
                        game.players[0].team, game.players[1].team = team_a, team_b

                        if game.outcome == Game.Outcome.FINISHED:
                            # Game is finished, assign the defeat/loses to label
                            log_message(
                                f"New game finished with the following outcome: {game.players[0].name.encode()} {game.players[0].outcome} v {game.players[1].name.encode()} {game.players[1].outcome} ({game.link})",
                                "update_new_games",
                            )
                            if game.players[0].outcome == WarzonePlayer.Outcome.WON:
                                # Left team wins
                                self.update_standings_with_game(
                                    team_standings,
                                    player_standings,
                                    team_a,
                                    game.players[0].name,
                                    game.players[0].id,
                                    tab[0:2],
                                    True,
                                )
                                self.update_standings_with_game(
                                    team_standings,
                                    player_standings,
                                    team_b,
                                    game.players[1].name,
                                    game.players[1].id,
                                    tab[0:2],
                                    False,
                                )
                            elif game.players[1].outcome == WarzonePlayer.Outcome.WON:
                                # Right team wins
                                self.update_standings_with_game(
                                    team_standings,
                                    player_standings,
                                    team_a,
                                    game.players[0].name,
                                    game.players[0].id,
                                    tab[0:2],
                                    False,
                                )
                                self.update_standings_with_game(
                                    team_standings,
                                    player_standings,
                                    team_b,
                                    game.players[1].name,
                                    game.players[1].id,
                                    tab[0:2],
                                    True,
                                )
                            else:
                                # Randomly assign win (probably because they voted to end)
                                left_team_won = bool(random.getrandbits(1))
                                self.update_standings_with_game(
                                    team_standings,
                                    player_standings,
                                    team_a,
                                    game.players[0].name,
                                    game.players[0].id,
                                    tab[0:2],
                                    left_team_won,
                                )
                                self.update_standings_with_game(
                                    team_standings,
                                    player_standings,
                                    team_b,
                                    game.players[1].name,
                                    game.players[1].id,
                                    tab[0:2],
                                    not left_team_won,
                                )
            log_message(
                f"Finished scoring games in {tab}",
                "update_new_games",
            )

        with open("data/standings_validate.json", "w", encoding="utf-8") as output_file:
            json.dump(
                jsonpickle.encode((team_standings, player_standings)), output_file
            )

    def score_2v2_game(
        self,
        game: WarzoneGame,
        teams: Tuple[str, str],
        tab: str,
        team_standings: Dict[str, TeamResult],
        player_standings: Dict[str, GameResult],
    ):
        players_by_team: Dict[str, List[WarzonePlayer]] = {teams[0]: [], teams[1]: []}
        for player in game.players:
            # Change player team from the Warzone integer into the actual team name (ex "4" -> "CAN")
            if player.team.isnumeric():
                player.team = TEAM_NAME_TO_API_VALUE.inverse[player.team]
            players_by_team[player.team].append(player)
        sorted_players: List[List[WarzonePlayer]] = list(
            map(lambda e: sorted(e), players_by_team.values())
        )

        # Ensure that players (by team) are in correct order of google sheets row
        if sorted_players[0][0].team != teams[0]:
            sorted_players.reverse()

        if game.outcome == Game.Outcome.FINISHED:
            # Game is finished, assign the defeat/loses to label
            log_message(
                f"New game finished with the following outcome: {game}",
                "update_new_games",
            )
            if any(
                player.outcome == WarzonePlayer.Outcome.WON
                for player in sorted_players[0]
            ):
                # Left team wins
                self.update_standings_with_2v2_game(
                    team_standings,
                    player_standings,
                    sorted_players[0][0].team,
                    sorted_players[0],
                    tab[0:2],
                    True,
                )
                self.update_standings_with_2v2_game(
                    team_standings,
                    player_standings,
                    sorted_players[1][0].team,
                    sorted_players[1],
                    tab[0:2],
                    False,
                )
            elif any(
                player.outcome == WarzonePlayer.Outcome.WON
                for player in sorted_players[1]
            ):
                # Right team wins
                self.update_standings_with_2v2_game(
                    team_standings,
                    player_standings,
                    sorted_players[0][0].team,
                    sorted_players[0],
                    tab[0:2],
                    False,
                )
                self.update_standings_with_2v2_game(
                    team_standings,
                    player_standings,
                    sorted_players[1][0].team,
                    sorted_players[1],
                    tab[0:2],
                    True,
                )
            else:
                # Randomly assign win (probably because they voted to end)
                left_team_won = bool(random.getrandbits(1))
                self.update_standings_with_2v2_game(
                    team_standings,
                    player_standings,
                    sorted_players[0][0].team,
                    sorted_players[0],
                    tab[0:2],
                    left_team_won,
                )
                self.update_standings_with_2v2_game(
                    team_standings,
                    player_standings,
                    sorted_players[1][0].team,
                    sorted_players[1],
                    tab[0:2],
                    not left_team_won,
                )

    def get_game_tabs(self) -> List[str]:
        """
        Returns a list of the google sheets tabs containing games.
        """
        game_tabs = []
        sheets = self.sheet.get_sheet_tabs_data()
        for tab in sheets:
            # Get the tabs that we should parse
            # Should be either `R# Games` or `R# Games 2v2`
            if re.search("^R\d Games", tab["properties"]["title"]):
                game_tabs.append(tab["properties"]["title"])
        return game_tabs

    def convert_wz_game_link_to_id(self, game_link: str):
        return game_link[43:]

    def update_standings_with_game(
        self,
        team_standings: Dict[str, TeamResult],
        player_standings: Dict[str, PlayerResult],
        team: str,
        player_name: str,
        player_id: int,
        round: str,
        is_won: bool,
    ):
        if is_won:
            team_standings.setdefault(team, TeamResult(team)).add_win(round)
            player_standings.setdefault(
                player_id, PlayerResult(player_name, player_id, team)
            ).wins += 1
        else:
            team_standings.setdefault(team, TeamResult(team)).add_loss(round)
            player_standings.setdefault(
                player_id, PlayerResult(player_name, player_id, team)
            ).losses += 1

    def update_standings_with_2v2_game(
        self,
        team_standings: Dict[str, TeamResult],
        player_standings: Dict[str, PlayerResult],
        team: str,
        players: List[WarzonePlayer],
        round: str,
        is_won: bool,
    ):
        if is_won:
            team_standings.setdefault(team, TeamResult(team)).add_win(round)
            for player in players:
                player_standings.setdefault(
                    player.id, PlayerResult(player.name, player.id, team)
                ).wins += 1
        else:
            team_standings.setdefault(team, TeamResult(team)).add_loss(round)
            for player in players:
                player_standings.setdefault(
                    player.id, PlayerResult(player.name, player.id, team)
                ).losses += 1

    def write_player_standings(self):
        _: Dict[str, TeamResult] = {}
        player_standings: Dict[str, PlayerResult] = {}
        with open("data/standings_validate.json", "r", encoding="utf-8") as input_file:
            _, player_standings = jsonpickle.decode(json.load(input_file))

        current_data = self.sheet.get_rows("Validate_Player_Stats!A1:E300")
        for row in current_data:
            if row and row[0] != "Name":
                row[3] = player_standings[row[1]].wins
                row[4] = player_standings[row[1]].losses
                player_standings.pop(row[1])
        for _, ps in player_standings.items():
            current_data.append([ps.name, ps.id, ps.team, ps.wins, ps.losses])

        log_message(
            f"Updated player stats with a total {len(current_data)} rows",
            "write_standings",
        )
        self.sheet.update_rows_raw(
            f"Validate_Player_Stats!A1:E{len(current_data)}", current_data
        )

    def write_team_standings(self):
        team_standings: Dict[str, TeamResult] = {}
        _: Dict[str, PlayerResult] = {}
        with open("data/standings_validate.json", "r", encoding="utf-8") as input_file:
            team_standings, _ = jsonpickle.decode(json.load(input_file))

        current_data = self.sheet.get_rows("Validate_Country_Stats!A1:E50")
        for row in current_data:
            if row and row[0] != "Country":
                row[1] = team_standings[row[0]].round_wins
                row[2] = team_standings[row[0]].round_losses
                row[3] = sum(
                    map(lambda e: e.wins, team_standings[row[0]].games_result.values())
                )
                row[4] = sum(
                    map(
                        lambda e: e.losses, team_standings[row[0]].games_result.values()
                    )
                )
                team_standings.pop(row[0])
        for _, ts in team_standings.items():
            current_data.append(
                [
                    ts.name,
                    ts.round_wins,
                    ts.round_losses,
                    sum(map(lambda e: e.wins, ts.games_result.values())),
                    sum(map(lambda e: e.losses, ts.games_result.values())),
                ]
            )

        log_message(
            f"Updated team stats with a total {len(current_data)} rows",
            "write_standings",
        )
        self.sheet.update_rows_raw(
            f"Validate_Country_Stats!A1:E{len(current_data)}", current_data
        )
