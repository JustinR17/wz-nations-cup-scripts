from datetime import datetime, timedelta, timezone
import json
import os
import random
from typing import Dict, List, Tuple

import jsonpickle
from NCTypes import (
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


class ParseGames:

    TAB_TO_GAME_RANGE_MAPPING = {
        "_Finals": "K2:R105",
        "_Main": "I3:P169",
        "_Qualifiers": "",
    }

    TAB_TO_TABLE_RANGE_MAPPING = {"_Finals": None, "_Main": "B3:G37", "_Qualifiers": ""}

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
            newly_finished_games, games_to_delete = self.update_new_games()
            self.delete_unstarted_games(games_to_delete)
            self.write_newly_finished_games(newly_finished_games)
            self.write_player_standings()
            self.write_team_standings()
        except Exception as e:
            log_exception(e)

    def update_new_games(
        self,
    ) -> Tuple[Dict[str, List[WarzoneGame]], List[WarzoneGame]]:
        """
        Checks all game tabs for games that have newly finished. Writes the new results in the tab.

        Returns a dictionary of lists ({round name -> List[Games])
        {
            phase: {
                round: List[Games]
            }
        }

        """

        team_standings: Dict[str, Dict[str, TeamResult]] = {}
        player_standings: Dict[str, Dict[str, GameResult]] = {}
        with open("data/standings.json", "r", encoding="utf-8") as input_file:
            team_standings, player_standings = jsonpickle.decode(json.load(input_file))

        newly_finished_games: Dict[str, Dict[str, List[WarzoneGame]]] = {}
        newly_finished_games_count = 0
        games_to_delete = []
        for tab in self.get_game_tabs():
            tab_phase = re.search("^(_\w+)", tab).group(1)
            tab_status = self.sheet.get_rows(f"{tab}!A1:B1")
            game_range = ParseGames.TAB_TO_GAME_RANGE_MAPPING[tab_phase]
            table_range = ParseGames.TAB_TO_TABLE_RANGE_MAPPING[tab_phase]
            round = tab[1:]

            tab_rows = self.sheet.get_rows(f"{tab}!{game_range}")
            tab_rows_formulas = self.sheet.get_rows_formulas(f"{tab}!{game_range}")
            table_rows = (
                self.sheet.get_rows(f"{tab}!{table_range}") if table_range else None
            )
            table_rows_formulas = (
                self.sheet.get_rows_formulas(f"{tab}!{table_range}")
                if table_range
                else None
            )
            if (
                not len(tab_rows)
                or not len(tab_rows[0])
                or "in-progress" not in tab_status[0][0]
            ):
                log_message(
                    f"Skipping the game log tab '{tab}' due to missing 'in-progress' tag",
                    "update_new_games",
                )
                continue
            log_message(f"Checking games in game log tab '{tab}'", "update_new_games")

            # TODO: update the score_row
            group, team_a, team_b, score_row = "", "", "", []
            for i, row in enumerate(tab_rows):
                if not row:
                    # Finished the previous matchup
                    team_a, team_b, score_row = "", "", []
                else:
                    if row[0]:
                        # update the current round/group
                        group = row[0]

                    if not team_a and not team_b:
                        # New teams to add
                        team_a, team_b, score_row = (
                            row[1].strip(),
                            row[4].strip(),
                            row,
                        )
                        if team_a:
                            log_message(
                                f"Checking games for {tab} - {team_a} vs {team_b}",
                                "update_new_games",
                            )
                    elif not row[3]:
                        # Game to check
                        game = self.api.check_game(
                            self.convert_wz_game_link_to_id(row[6].strip())
                        )
                        if game.players[0].id != row[1].strip():
                            game.players.reverse()
                        game.players[0].team, game.players[1].team = team_a, team_b
                        game.players[0].score, game.players[1].score = (
                            int(score_row[2]),
                            int(score_row[5]),
                        )

                        # Game is not finished, but we will update the progress (ie round or stage)
                        while len(tab_rows_formulas[i]) < 8:
                            tab_rows_formulas[i].append("")
                        if game.outcome == Game.Outcome.WAITING_FOR_PLAYERS:
                            tab_rows_formulas[i][7] = "Lobby"
                        elif game.outcome == Game.Outcome.DISTRIBUTING_TERRITORIES:
                            tab_rows_formulas[i][8] = "Picks"
                        else:
                            tab_rows_formulas[i][8] = f"Turn {game.round}"

                        # declined_players = [str(player) for player in game.players if player.outcome == WarzonePlayer.Outcome.DECLINED]
                        # if len(declined_players):
                        #     log_message(f"Game at lobby with declined player(s): {', '.join(declined_players)}", 'parseGames.update_new_games')

                        # if game.outcome == Game.Outcome.WAITING_FOR_PLAYERS:
                        #     invited_players = [str(player) for player in game.players if player.outcome == WarzonePlayer.Outcome.INVITED]
                        #     print(f"{game.link} - nonjoin after: {(game.start_time + timedelta(days=4)).isoformat()} {', '.join(invited_players)}")

                        if game.outcome == Game.Outcome.FINISHED:
                            # Game is finished, assign the defeat/loses to label
                            log_message(
                                f"New game finished with the following outcome: {game.players[0].name.encode()} {game.players[0].outcome} v {game.players[1].name.encode()} {game.players[1].outcome} ({game.link})",
                                "update_new_games",
                            )
                            newly_finished_games.setdefault(round, {}).setdefault(
                                group, []
                            ).append(game)
                            newly_finished_games_count += 1
                            if game.players[0].outcome == WarzonePlayer.Outcome.WON:
                                # Left team wins
                                loser = game.players[1]
                                tab_rows_formulas[i][3] = "defeats"
                                game.players[0].score += 1
                                game.winner = [game.players[0].id]
                                # TODO: update this function and arguments
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
                                loser = game.players[0]
                                tab_rows_formulas[i][3] = "loses to"
                                game.players[1].score += 1
                                game.winner = [game.players[1].id]
                                # TODO: update this function and arguments
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
                                loser = game.players[int(left_team_won)]
                                tab_rows_formulas[i][3] = (
                                    "defeats" if left_team_won else "loses to"
                                )
                                game.players[0 if left_team_won else 1].score += 1
                                game.winner = [
                                    game.players[0 if left_team_won else 1].id
                                ]
                                # TODO: update this function and arguments
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
                            if loser.outcome == WarzonePlayer.Outcome.BOOTED:
                                tab_rows_formulas[i][7] = f"Turn {game.round} - Booted"

                        elif (
                            game.outcome == Game.Outcome.WAITING_FOR_PLAYERS
                            and datetime.now(timezone.utc) - game.start_time
                            > timedelta(days=4)
                        ):
                            # Game has been in the join lobby for too long. Game will be deleted and appropriate winner selected according to algorithm:
                            # 1. Assign win to left player if they have joined, or are invited and the right player declined
                            # 2. Assign win to the right player if they have joined, or are invited and the left player declined
                            # 3. Randomly assign win if both players are invited, or declined
                            log_message(
                                f"New game passed join time: {game.players[0].name.encode()} {game.players[0].outcome} v {game.players[1].name.encode()} {game.players[1].outcome} ({game.link})",
                                "update_new_games",
                            )
                            log_message(f"Storing end response: {game}")
                            newly_finished_games.setdefault(tab, []).append(game)
                            newly_finished_games_count += 1
                            tab_rows_formulas[i][7] = "Deleted"
                            if game.players[
                                0
                            ].outcome == WarzonePlayer.Outcome.PLAYING or (
                                game.players[0].outcome == WarzonePlayer.Outcome.INVITED
                                and game.players[1].outcome
                                == WarzonePlayer.Outcome.DECLINED
                            ):
                                # Left team wins
                                tab_rows_formulas[i][3] = "defeats"
                                game.players[0].score += 1
                                game.winner = [game.players[0].id]
                                # TODO: update this function and arguments
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
                            elif game.players[
                                1
                            ].outcome == WarzonePlayer.Outcome.PLAYING or (
                                game.players[1].outcome == WarzonePlayer.Outcome.INVITED
                                and game.players[0].outcome
                                == WarzonePlayer.Outcome.DECLINED
                            ):
                                # Right team wins
                                tab_rows_formulas[i][3] = "loses to"
                                game.players[1].score += 1
                                game.winner = [game.players[1].id]
                                # TODO: update this function and arguments
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
                                # Some weird combo where neither player accepted
                                # Randomly assign winner
                                left_team_won = bool(random.getrandbits(1))
                                tab_rows_formulas[i][3] = (
                                    "defeats" if left_team_won else "loses to"
                                )
                                game.players[0 if left_team_won else 1].score += 1
                                game.winner = [
                                    game.players[0 if left_team_won else 1].id
                                ]
                                # TODO: update this function and arguments
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

                            games_to_delete.append(game)

            # TODO: update data tables
            if table_rows:
                group = ""
                for i, row in enumerate(table_rows):
                    if not row:
                        group = ""
                    elif not group:
                        # group section
                        group = row[0]
                    elif row[1] == "Wins Adjusted":
                        # table headings row... ignore
                        continue
                    else:
                        # Parse team results
                        if row[0].strip() in team_standings:
                            row[2] = (
                                team_standings[row[0].strip()]
                                .games_result[f"{round}-{group}"]
                                .wins
                            )
                            row[3] = (
                                team_standings[row[0].strip()]
                                .games_result[f"{round}-{group}"]
                                .losses
                            )
                self.sheet.update_rows_raw(f"{tab}!{table_range}", table_rows)

            # Add the last updated time to the sheet so people know when it is broken
            if len(tab_status[0]) < 2:
                # Likely only 5 elements then
                tab_status[0].append(datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
            else:
                # Overwrite previous value
                tab_status[0][1] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            self.sheet.update_rows_raw(f"{tab}!A1:B1", tab_rows)
            self.sheet.update_rows_raw(f"{tab}!{game_range}", tab_rows)
            log_message(
                f"Finished updating games in {tab}. Newly finished games: {newly_finished_games_count}; games to delete: {len(games_to_delete)}",
                "update_new_games",
            )

        # Raw file that is used by scripts
        with open("data/standings.json", "w", encoding="utf-8") as output_file:
            json.dump(
                jsonpickle.encode((team_standings, player_standings)), output_file
            )
        # Prettified version in case manual changes are needed
        with open("data/standings_pretty.json", "w", encoding="utf-8") as output_file:
            json.dump((team_standings, player_standings), output_file, indent=4)

        return newly_finished_games, games_to_delete

    def get_game_tabs(self) -> List[str]:
        """
        Returns a list of the google sheets tabs containing games.
        """
        game_tabs = []
        sheets = self.sheet.get_sheet_tabs_data()
        for tab in sheets:
            # Get the tabs that we should parse
            # Should be any tab that starts with "_"
            if re.search("^_", tab["properties"]["title"]):
                game_tabs.append(tab["properties"]["title"])
        return game_tabs

    def convert_wz_game_link_to_id(self, game_link: str):
        return game_link[43:]

    def delete_unstarted_games(self, games_to_delete: List[WarzoneGame]):
        """
        Deletes a list of warzone games that have not begun yet through the WZ API.
        """
        failed_to_delete_games = []
        for game in games_to_delete:
            log_message(
                f"Deleting the following game: {game}", "delete_unstarted_games"
            )
            try:
                self.api.delete_game(int(self.convert_wz_game_link_to_id(game.link)))
            except Exception as e:
                failed_to_delete_games.append(game)
                log_exception(f"Unable to delete game {game.link}:\n{e}")

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
            team_standings[team].add_win(round)
            player_standings.setdefault(
                player_id, PlayerResult(player_name, player_id, team)
            ).wins += 1
        else:
            team_standings[team].add_loss(round)
            player_standings.setdefault(
                player_id, PlayerResult(player_name, player_id, team)
            ).losses += 1

    def write_player_standings(self):
        _: Dict[str, TeamResult] = {}
        player_standings: Dict[str, PlayerResult] = {}
        with open("data/standings.json", "r", encoding="utf-8") as input_file:
            _, player_standings = jsonpickle.decode(json.load(input_file))

        current_data = self.sheet.get_rows("Player_Stats!A2:E300")
        for row in current_data:
            if row:
                row[3] = player_standings[row[1]].wins
                row[4] = player_standings[row[1]].losses
                player_standings.pop(row[1])
        for _, ps in player_standings.items():
            current_data.append([ps.name, ps.id, ps.team, ps.wins, ps.losses])

        log_message(
            f"Updated player stats with a total {len(current_data)} rows",
            "write_standings",
        )
        self.sheet.update_rows_raw("Player_Stats!A2:E300", current_data)

    def write_team_standings(self):
        team_standings: Dict[str, TeamResult] = {}
        _: Dict[str, PlayerResult] = {}
        with open("data/standings.json", "r", encoding="utf-8") as input_file:
            team_standings, _ = jsonpickle.decode(json.load(input_file))

        current_data = self.sheet.get_rows("Country_Stats!A1:E50")
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
            f"Country_Stats!A1:E{len(current_data)}", current_data
        )

    def write_newly_finished_games(
        self, newly_finished_games: Dict[str, List[WarzoneGame]]
    ):
        """
        Combines the existing newly_finished_games that have not been posted yet with the newly finished games from this check
        """

        if not os.path.isfile("data/newly_finished_games.json"):
            with open(
                "data/newly_finished_games.json", "w", encoding="utf-8"
            ) as output_file:
                json.dump(jsonpickle.encode({}), output_file)
        with open(
            "data/newly_finished_games.json", "r", encoding="utf-8"
        ) as input_file:
            buffer_newly_finished_games = jsonpickle.decode(json.load(input_file))
            conmbined_newly_finished = {
                key: buffer_newly_finished_games.get(key, [])
                + newly_finished_games.get(key, [])
                for key in set(
                    list(buffer_newly_finished_games.keys())
                    + list(newly_finished_games.keys())
                )
            }

        with open(
            "data/newly_finished_games.json", "w", encoding="utf-8"
        ) as output_file:
            log_message(
                "JSON version of newly finished games saved to 'newly_finished_games.json'",
                "write_newly_finished_games",
            )
            json.dump(jsonpickle.encode(conmbined_newly_finished), output_file)
