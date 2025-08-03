from datetime import datetime, timedelta, timezone
import json
import os
import random
from typing import Dict, List, Tuple

import jsonpickle
from NCTypes import (
    Game,
    PlayerResult,
    TableTeamResult,
    WarzoneGame,
    WarzonePlayer,
)
from api import API
from data import (
    NO_GAME_PLAYED,
    TAB_TO_GAME_RANGE_MAPPING,
    TAB_TO_TABLE_RANGE_MAPPING,
    CGAMES_TAB_TO_TABLE_RANGE_MAPPING,
    UNKNOWN_PLAYER_NAME,
)
from sheet import GoogleSheet
import re

from utils import log_exception, log_message


class ParseGames:

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
            tabs_to_update = self.sheet.get_tabs_by_status(
                [GoogleSheet.TabStatus.IN_PROGRESS, GoogleSheet.TabStatus.FINISHED]
            )
            log_message(
                f"The following tabs are in-progress: '{tabs_to_update}'",
                "ParseGames.run",
            )
            team_table_results = self.parse_team_table_results(tabs_to_update)
            newly_finished_games, games_to_delete, team_results, player_results = (
                self.update_new_games(team_table_results, tabs_to_update)
            )
            print(f"\n\n=================\nGames to delete:\n{games_to_delete}")
            self.delete_unstarted_games(games_to_delete)
            self.write_newly_finished_games(newly_finished_games)
            self.write_player_standings(player_results)
            self.write_team_standings(team_results)
        except Exception as e:
            log_exception(e)

    def parse_team_table_results(self, tabs: List[str]) -> Dict[str, TableTeamResult]:
        team_table_results: Dict[str, TableTeamResult] = {}
        for tab in tabs:
            tab_phase = re.search("^(_\w+)", tab).group(1)
            table_range = TAB_TO_TABLE_RANGE_MAPPING[tab_phase]
            round = tab[1:]

            table_rows_values = self.sheet.get_rows(f"{tab}!{table_range}")

            #######################
            ##### Parse Table #####
            #######################
            group = ""
            for row in table_rows_values:
                row.extend("" for _ in range(7 - len(row)))
                if not row[0] and not row[1]:
                    group = ""
                elif not group:
                    # group section
                    group = row[0]
                else:
                    if row[0]:
                        # update group if finals tab (no divider between rounds)
                        group = row[0]
                    # Parse team results
                    team_table_results[f"{round}-{group}-{row[1]}"] = TableTeamResult(
                        round, group, row[1], row[2], row[3], row[4]
                    )
        return team_table_results

    def sum_team_standings_in_phase(
        self,
        team_table_results: Dict[str, TableTeamResult],
        phase: str,
        group: str,
        team: str,
    ) -> Tuple[int, float, int]:
        matched_elements = [
            e[1]
            for e in team_table_results.items()
            if phase in e[0] and f"{group}-{team}" in e[0]
        ]
        return (
            sum([e.wins for e in matched_elements]),
            sum([e.wins_adjusted for e in matched_elements]),
            sum([e.losses for e in matched_elements]),
        )

    def update_new_games(
        self, team_table_results: Dict[str, TableTeamResult], tabs: List[str]
    ):
        """
        Checks all game tabs for games that have newly finished. Writes the new results in the tab.

        Returns a dictionary of lists ({round name -> List[Games])
        {
            phase: {
                round: List[Games]
            }
        }

        """

        newly_finished_games: Dict[str, List[WarzoneGame]] = {}
        newly_finished_games_count = 0
        games_to_delete: List[WarzoneGame] = []
        player_results: Dict[int, PlayerResult] = {}
        for tab in tabs:
            tab_phase = re.search("^(_\w+)", tab).group(1)
            tab_status = self.sheet.get_rows(f"{tab}!A1:B1")
            game_range = TAB_TO_GAME_RANGE_MAPPING[tab_phase]
            table_range = CGAMES_TAB_TO_TABLE_RANGE_MAPPING[tab_phase]
            round = tab[1:]

            tab_rows_values = self.sheet.get_rows(f"{tab}!{game_range}")
            table_rows_values = (
                self.sheet.get_rows(f"{tab}!{table_range}") if table_range else []
            )
            table_rows_formulas = (
                self.sheet.get_rows_formulas(f"{tab}!{table_range}")
                if table_range
                else []
            )

            log_message(
                f"Checking games in game log tab '{tab}' - {len(tab_rows_values)}",
                "update_new_games",
            )
            #######################
            ##### Parse Games #####
            #######################
            group, team_a, team_b, score_row = "", "", "", []
            for row in tab_rows_values:
                row.extend("" for _ in range(9 - len(row)))
                if (not row[0] and not row[1]) or (not row[3] and not row[6]):
                    # Finished the previous matchup
                    team_a, team_b, score_row = "", "", []
                else:
                    if row[0]:
                        # update the current round/group
                        group = row[0]

                    if not team_a and not team_b and row[1]:
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
                        # check if a game has been created (ie. there are players on both teams)
                        if not row[6]:
                            # No game, one or both players are missing
                            row[3] = NO_GAME_PLAYED
                            team_table_results[
                                f"{round}-{group}-{team_a}"
                            ].unstarted_games += 1
                            team_table_results[
                                f"{round}-{group}-{team_b}"
                            ].unstarted_games += 1
                            continue

                        # Game to check
                        game = self.api.check_game(
                            self.convert_wz_game_link_to_id(row[6].strip())
                        )
                        if game.players[0].id != int(
                            re.search(r"^.*?p=(\d*).*$", row[2]).group(1)
                        ):
                            game.players.reverse()
                        game.players[0].team, game.players[1].team = team_a, team_b
                        game.players[0].score, game.players[1].score = (
                            self.sum_team_standings_in_phase(
                                team_table_results, tab_phase[1:], group, team_a
                            )[1],
                            self.sum_team_standings_in_phase(
                                team_table_results, tab_phase[1:], group, team_b
                            )[1],
                        )

                        # Game is not finished, but we will update the progress (ie round or stage)
                        if game.outcome == Game.Outcome.WAITING_FOR_PLAYERS:
                            row[7] = "Lobby"
                        elif game.outcome == Game.Outcome.DISTRIBUTING_TERRITORIES:
                            row[7] = "Picks"
                        else:
                            row[7] = f"Turn {game.round}"

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
                            newly_finished_games.setdefault(
                                f"{round}-{group}", []
                            ).append(game)
                            newly_finished_games_count += 1
                            if game.players[0].outcome == WarzonePlayer.Outcome.WON:
                                # Left team wins
                                loser = game.players[1]
                                row[3] = "defeats"
                                game.players[0].score += 1
                                score_row[2] = int(score_row[2]) + 1
                                game.winner = [game.players[0].id]
                                self.update_team_table_results(
                                    team_table_results[f"{round}-{group}-{team_a}"],
                                    True,
                                )
                                self.update_team_table_results(
                                    team_table_results[f"{round}-{group}-{team_b}"],
                                    False,
                                )
                                self.update_standings_with_game(
                                    player_results,
                                    team_a,
                                    game.players[0].name,
                                    game.players[0].id,
                                    True,
                                )
                                self.update_standings_with_game(
                                    player_results,
                                    team_b,
                                    game.players[1].name,
                                    game.players[1].id,
                                    False,
                                )
                            elif game.players[1].outcome == WarzonePlayer.Outcome.WON:
                                # Right team wins
                                loser = game.players[0]
                                row[3] = "loses to"
                                game.players[1].score += 1
                                score_row[5] = int(score_row[5]) + 1
                                game.winner = [game.players[1].id]
                                self.update_team_table_results(
                                    team_table_results[f"{round}-{group}-{team_a}"],
                                    False,
                                )
                                self.update_team_table_results(
                                    team_table_results[f"{round}-{group}-{team_b}"],
                                    True,
                                )
                                self.update_standings_with_game(
                                    player_results,
                                    team_a,
                                    game.players[0].name,
                                    game.players[0].id,
                                    False,
                                )
                                self.update_standings_with_game(
                                    player_results,
                                    team_b,
                                    game.players[1].name,
                                    game.players[1].id,
                                    True,
                                )
                            else:
                                # Randomly assign win (probably because they voted to end)
                                left_team_won = bool(random.getrandbits(1))
                                loser = game.players[int(left_team_won)]
                                row[3] = "defeats" if left_team_won else "loses to"
                                game.players[0 if left_team_won else 1].score += 1
                                score_row[2 if left_team_won else 5] = (
                                    int(score_row[2 if left_team_won else 5]) + 1
                                )
                                game.winner = [
                                    game.players[0 if left_team_won else 1].id
                                ]
                                self.update_team_table_results(
                                    team_table_results[f"{round}-{group}-{team_a}"],
                                    left_team_won,
                                )
                                self.update_team_table_results(
                                    team_table_results[f"{round}-{group}-{team_b}"],
                                    not left_team_won,
                                )
                                self.update_standings_with_game(
                                    player_results,
                                    team_a,
                                    game.players[0].name,
                                    game.players[0].id,
                                    left_team_won,
                                )
                                self.update_standings_with_game(
                                    player_results,
                                    team_b,
                                    game.players[1].name,
                                    game.players[1].id,
                                    not left_team_won,
                                )
                            if loser.outcome == WarzonePlayer.Outcome.BOOTED:
                                row[7] = f"Turn {game.round} - Booted"

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
                            newly_finished_games.setdefault(
                                f"{round}-{group}", []
                            ).append(game)
                            newly_finished_games_count += 1
                            row[7] = "Deleted"
                            if game.players[
                                0
                            ].outcome == WarzonePlayer.Outcome.PLAYING or (
                                game.players[0].outcome == WarzonePlayer.Outcome.INVITED
                                and game.players[1].outcome
                                == WarzonePlayer.Outcome.DECLINED
                            ):
                                # Left team wins
                                row[3] = "defeats"
                                game.players[0].score += 1
                                score_row[2] = int(score_row[2]) + 1
                                game.winner = [game.players[0].id]
                                self.update_team_table_results(
                                    team_table_results[f"{round}-{group}-{team_a}"],
                                    True,
                                )
                                self.update_team_table_results(
                                    team_table_results[f"{round}-{group}-{team_b}"],
                                    False,
                                )
                                self.update_standings_with_game(
                                    player_results,
                                    team_a,
                                    game.players[0].name,
                                    game.players[0].id,
                                    True,
                                )
                                self.update_standings_with_game(
                                    player_results,
                                    team_b,
                                    game.players[1].name,
                                    game.players[1].id,
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
                                row[3] = "loses to"
                                game.players[1].score += 1
                                score_row[5] = int(score_row[5]) + 1
                                game.winner = [game.players[1].id]
                                self.update_team_table_results(
                                    team_table_results[f"{round}-{group}-{team_a}"],
                                    False,
                                )
                                self.update_team_table_results(
                                    team_table_results[f"{round}-{group}-{team_b}"],
                                    True,
                                )
                                self.update_standings_with_game(
                                    player_results,
                                    team_a,
                                    game.players[0].name,
                                    game.players[0].id,
                                    False,
                                )
                                self.update_standings_with_game(
                                    player_results,
                                    team_b,
                                    game.players[1].name,
                                    game.players[1].id,
                                    True,
                                )
                            else:
                                # Some weird combo where neither player accepted
                                # Randomly assign winner
                                left_team_won = bool(random.getrandbits(1))
                                row[3] = "defeats" if left_team_won else "loses to"
                                game.players[0 if left_team_won else 1].score += 1
                                game.winner = [
                                    game.players[0 if left_team_won else 1].id
                                ]
                                score_row[2 if left_team_won else 5] = (
                                    int(score_row[2 if left_team_won else 5]) + 1
                                )
                                self.update_team_table_results(
                                    team_table_results[f"{round}-{group}-{team_a}"],
                                    left_team_won,
                                )
                                self.update_team_table_results(
                                    team_table_results[f"{round}-{group}-{team_b}"],
                                    not left_team_won,
                                )
                                self.update_standings_with_game(
                                    player_results,
                                    team_a,
                                    game.players[0].name,
                                    game.players[0].id,
                                    left_team_won,
                                )
                                self.update_standings_with_game(
                                    player_results,
                                    team_b,
                                    game.players[1].name,
                                    game.players[1].id,
                                    not left_team_won,
                                )

                            games_to_delete.append(game)
                    else:
                        # Game is already done, but add the win to player standings
                        if row[3] == NO_GAME_PLAYED:
                            # No game, one or both players are missing
                            team_table_results[
                                f"{round}-{group}-{team_a}"
                            ].unstarted_games += 1
                            team_table_results[
                                f"{round}-{group}-{team_b}"
                            ].unstarted_games += 1
                            continue

                        left_player_id = int(
                            re.search(r"^.*?p=(\d*).*$", row[2]).group(1)
                        )
                        right_player_id = int(
                            re.search(r"^.*?p=(\d*).*$", row[5]).group(1)
                        )
                        is_left_player_winner = row[3] == "defeats"

                        # winner
                        player_results.setdefault(
                            (
                                left_player_id
                                if is_left_player_winner
                                else right_player_id
                            ),
                            PlayerResult(
                                row[1] if is_left_player_winner else row[4],
                                (
                                    left_player_id
                                    if is_left_player_winner
                                    else right_player_id
                                ),
                                team_a if is_left_player_winner else team_b,
                            ),
                        ).wins += 1

                        # loser
                        player_results.setdefault(
                            (
                                left_player_id
                                if not is_left_player_winner
                                else right_player_id
                            ),
                            PlayerResult(
                                row[1] if not is_left_player_winner else row[4],
                                (
                                    left_player_id
                                    if not is_left_player_winner
                                    else right_player_id
                                ),
                                team_a if not is_left_player_winner else team_b,
                            ),
                        ).losses += 1

            #######################
            ##### Parse Table #####
            #######################
            if table_rows_values:
                group = ""
                for i, row in enumerate(table_rows_values):
                    row.extend("" for _ in range(7 - len(row)))
                    if not row[0] and not row[1]:
                        group = ""
                    elif not group:
                        # group section
                        group = row[0]
                    else:
                        # Parse team results
                        table_rows_formulas[i][3] = team_table_results[
                            f"{round}-{group}-{row[1]}"
                        ].wins
                        table_rows_formulas[i][4] = team_table_results[
                            f"{round}-{group}-{row[1]}"
                        ].losses
                self.sheet.update_rows_raw(f"{tab}!{table_range}", table_rows_formulas)

            # Add the last updated time to the sheet so people know when it is broken
            if len(tab_status[0]) < 2:
                tab_status[0].append(datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
            else:
                # Overwrite previous value
                tab_status[0][1] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            self.sheet.update_rows_raw(f"{tab}!A1:B1", tab_status)
            self.sheet.update_rows_raw(f"{tab}!{game_range}", tab_rows_values)
            log_message(
                f"Finished updating games in {tab}. Newly finished games: {newly_finished_games_count}; games to delete: {len(games_to_delete)}",
                "update_new_games",
            )

        return newly_finished_games, games_to_delete, team_table_results, player_results

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
        player_standings: Dict[int, PlayerResult],
        team: str,
        player_name: str,
        player_id: int,
        is_won: bool,
    ):
        if is_won:
            player_standings.setdefault(
                player_id, PlayerResult(player_name, player_id, team)
            ).wins += 1
        else:
            player_standings.setdefault(
                player_id, PlayerResult(player_name, player_id, team)
            ).losses += 1

    def update_team_table_results(self, team_result: TableTeamResult, is_won: bool):
        if is_won:
            team_result.wins_adjusted += 1
            team_result.wins += 1
        else:
            team_result.losses += 1

    def convert_wz_game_link_to_id(self, game_link: str):
        return game_link[43:]

    def write_player_standings(self, player_results: Dict[int, PlayerResult]):
        current_data = self.sheet.get_rows("Player Standings!A2:E300")
        for row in current_data:
            if row:
                row[3] = player_results[int(row[1])].wins
                row[4] = player_results[int(row[1])].losses
                player_results.pop(int(row[1]))
        for _, ps in player_results.items():
            current_data.append([ps.name, ps.id, ps.team, ps.wins, ps.losses])

        log_message(
            f"Updated player stats with a total {len(current_data)} rows",
            "write_standings",
        )
        self.sheet.update_rows_raw("Player Standings!A2:E300", current_data)

    def write_team_standings(self, team_results: Dict[str, TableTeamResult]):
        current_data = self.sheet.get_rows("Team Standings!A1:C50")
        seen_countries = set()
        for row in current_data:
            if row and row[0] != "Country":
                row[1] = sum(
                    [
                        result[1].wins
                        for result in team_results.items()
                        if row[0] in result[0].split("-")[2]
                    ]
                )
                row[2] = sum(
                    [
                        result[1].losses
                        for result in team_results.items()
                        if row[0] in result[0].split("-")[2]
                    ]
                )
                seen_countries.add(row[0])
        for key, ts in team_results.items():
            if key.split("-")[2] not in seen_countries:
                current_data.append(
                    [
                        ts.team,
                        ts.wins,
                        ts.losses,
                    ]
                )

        log_message(
            f"Updated team stats with a total {len(current_data)} rows",
            "write_standings",
        )
        self.sheet.update_rows_raw(
            f"Team Standings!A1:C{len(current_data)}", current_data
        )
        with open("data/team_standings.json", "w", encoding="utf-8") as output_file:
            log_message(
                "JSON version of newly finished games saved to 'team_standings.json'",
                "write_team_standings",
            )
            json.dump(jsonpickle.encode(team_results), output_file)

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
