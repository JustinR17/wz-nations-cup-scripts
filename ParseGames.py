from datetime import datetime, timedelta, timezone
import json
import os
import random
from typing import Dict, List, Tuple

import jsonpickle
from NCTypes import TEAM_NAME_TO_API_VALUE, Game, GameResult, PlayerResult, TeamResult, WarzoneGame, WarzonePlayer
from api import API
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
            newly_finished_games, games_to_delete = self.update_new_games()
            self.delete_unstarted_games(games_to_delete)
            self.write_newly_finished_games(newly_finished_games)
            self.write_player_standings()
            self.write_team_standings()
        except Exception as e:
            log_exception(e)

    
    def update_new_games(self) -> Tuple[Dict[str, List[WarzoneGame]], List[WarzoneGame]]:
        """
        Checks all game tabs for games that have newly finished. Writes the new results in the tab.

        Returns a dictionary of lists (tab name -> List[Games])
        """

        team_standings: Dict[str, TeamResult] = {}
        player_standings: Dict[str, GameResult] = {}
        with open("data/standings.json", "r", encoding="utf-8") as input_file:
            team_standings, player_standings = jsonpickle.decode(json.load(input_file))
        
        newly_finished_games: Dict[str, List[WarzoneGame]] = {}
        newly_finished_games_count = 0
        games_to_delete = []
        for tab in self.get_game_tabs():
            is_2v2 = "2v2" in tab
            tab_rows = self.sheet.get_rows(f"{tab}!A1:{'K' if is_2v2 else'G'}300")
            if not len(tab_rows) or not len(tab_rows[0]) or "in-progress" not in tab_rows[0][0]:
                log_message(f"Skipping the game log tab '{tab}' due to missing 'in-progress' tag", "update_new_games")
                continue
            log_message(f"Checking games in game log tab '{tab}'", "update_new_games")

            team_a, team_b, score_row = "", "", []
            for i, row in enumerate(tab_rows):
                if i == 0:
                    continue
                if not row:
                    # Finished the previous matchup
                    team_a, team_b, score_row = "", "", []
                else:
                    if not team_a and not team_b:
                        # New teams to add
                        team_a, team_b, score_row = row[0].strip(), row[5 if is_2v2 else 3].strip(), row
                        if team_a:
                            log_message(f"Checking games for {tab} - {team_a} vs {team_b}", "update_new_games")
                    elif not row[4 if is_2v2 else 2]:
                        # Game to check
                        # 2v2 requires more advanced logic that is separated out for now
                        print(row)
                        game = self.api.check_game(self.convert_wz_game_link_to_id(row[9 if is_2v2 else 5].strip()))

                        if is_2v2:
                            # Separate workflow for 2v2 games that will be extended to any XvX games
                            print(f"Running the 2v2 workflow")
                            newly_finished_games_count += self.score_2v2_game(
                                game, row, (team_a, team_b), tab, score_row, team_standings,
                                player_standings, newly_finished_games, games_to_delete
                            )
                            continue
                        print(f"Running the 1v1 workflow")

                        if game.players[0].id != row[1].strip():
                            game.players.reverse()
                        game.players[0].team, game.players[1].team = team_a,  team_b
                        game.players[0].score, game.players[1].score = int(score_row[1]), int(score_row[4])

                        # Game is not finished, but we will update the progress (ie round or stage)
                        while len(row) < 7:
                            row.append("")
                        if game.outcome == Game.Outcome.WAITING_FOR_PLAYERS:
                            row[6] = "Lobby"
                        elif game.outcome == Game.Outcome.DISTRIBUTING_TERRITORIES:
                            row[6] = "Picks"
                        else:
                            row[6] = f"Turn {game.round+1}"

                        # declined_players = [str(player) for player in game.players if player.outcome == WarzonePlayer.Outcome.DECLINED]
                        # if len(declined_players):
                        #     log_message(f"Game at lobby with declined player(s): {', '.join(declined_players)}", 'parseGames.update_new_games')
                        
                        # if game.outcome == Game.Outcome.WAITING_FOR_PLAYERS:
                        #     invited_players = [str(player) for player in game.players if player.outcome == WarzonePlayer.Outcome.INVITED]
                        #     print(f"{game.link} - nonjoin after: {(game.start_time + timedelta(days=4)).isoformat()} {', '.join(invited_players)}")

                        if game.outcome == Game.Outcome.FINISHED:
                            # Game is finished, assign the defeat/loses to label
                            log_message(f"New game finished with the following outcome: {game.players[0].name.encode()} {game.players[0].outcome} v {game.players[1].name.encode()} {game.players[1].outcome} ({game.link})", "update_new_games")
                            newly_finished_games.setdefault(tab, []).append(game)
                            newly_finished_games_count += 1
                            if game.players[0].outcome == WarzonePlayer.Outcome.WON:
                                # Left team wins
                                loser = game.players[1]
                                row[2] = "defeats"
                                score_row[1] = int(score_row[1]) + 1
                                game.players[0].score += 1
                                game.winner = [game.players[0].id]
                                self.update_standings_with_game(team_standings, player_standings, team_a, game.players[0].name, game.players[0].id, tab[0:2], True)
                                self.update_standings_with_game(team_standings, player_standings, team_b, game.players[1].name, game.players[1].id, tab[0:2], False)
                            elif game.players[1].outcome == WarzonePlayer.Outcome.WON:
                                # Right team wins
                                loser = game.players[0]
                                row[2] = "loses to"
                                score_row[4] = int(score_row[4]) + 1
                                game.players[1].score += 1
                                game.winner = [game.players[1].id]
                                self.update_standings_with_game(team_standings, player_standings, team_a, game.players[0].name, game.players[0].id, tab[0:2], False)
                                self.update_standings_with_game(team_standings, player_standings, team_b, game.players[1].name, game.players[1].id, tab[0:2], True)
                            else:
                                # Randomly assign win (probably because they voted to end)
                                left_team_won = bool(random.getrandbits(1))
                                loser = game.players[int(left_team_won)]
                                row[2] = "defeats" if left_team_won else "loses to"
                                score_row[1 if left_team_won else 4] = int(score_row[1 if left_team_won else 4]) + 1
                                game.players[0 if left_team_won else 1].score += 1
                                game.winner = [game.players[0 if left_team_won else 1].id]
                                self.update_standings_with_game(team_standings, player_standings, team_a, game.players[0].name, game.players[0].id, tab[0:2], left_team_won)
                                self.update_standings_with_game(team_standings, player_standings, team_b, game.players[1].name, game.players[1].id, tab[0:2], not left_team_won)
                            if loser.outcome == WarzonePlayer.Outcome.BOOTED:
                                row[6] = f"Turn {game.round+1} - Booted"
                        
                        elif game.outcome == Game.Outcome.WAITING_FOR_PLAYERS and datetime.now(timezone.utc) - game.start_time > timedelta(days=4):
                            # Game has been in the join lobby for too long. Game will be deleted and appropriate winner selected according to algorithm:
                            # 1. Assign win to left player if they have joined, or are invited and the right player declined
                            # 2. Assign win to the right player if they have joined, or are invited and the left player declined
                            # 3. Randomly assign win if both players are invited, or declined
                            log_message(f"New game passed join time: {game.players[0].name.encode()} {game.players[0].outcome} v {game.players[1].name.encode()} {game.players[1].outcome} ({game.link})", "update_new_games")
                            log_message(f"Storing end response: {game}")
                            newly_finished_games.setdefault(tab, []).append(game)
                            newly_finished_games_count += 1
                            row[6] = "Deleted"
                            if game.players[0].outcome == WarzonePlayer.Outcome.PLAYING or \
                                (game.players[0].outcome == WarzonePlayer.Outcome.INVITED and game.players[1].outcome == WarzonePlayer.Outcome.DECLINED):
                                # Left team wins
                                row[2] = "defeats"
                                score_row[1] = int(score_row[1]) + 1
                                game.players[0].score += 1
                                game.winner = [game.players[0].id]
                                self.update_standings_with_game(team_standings, player_standings, team_a, game.players[0].name, game.players[0].id, tab[0:2], True)
                                self.update_standings_with_game(team_standings, player_standings, team_b, game.players[1].name, game.players[1].id, tab[0:2], False)
                            elif game.players[1].outcome == WarzonePlayer.Outcome.PLAYING or \
                                (game.players[1].outcome == WarzonePlayer.Outcome.INVITED and game.players[0].outcome == WarzonePlayer.Outcome.DECLINED):
                                # Right team wins
                                row[2] = "loses to"
                                score_row[4] = int(score_row[4]) + 1
                                game.players[1].score += 1
                                game.winner = [game.players[1].id]
                                self.update_standings_with_game(team_standings, player_standings, team_a, game.players[0].name, game.players[0].id, tab[0:2], False)
                                self.update_standings_with_game(team_standings, player_standings, team_b, game.players[1].name, game.players[1].id, tab[0:2], True)
                            else:
                                # Some weird combo where neither player accepted
                                # Randomly assign winner
                                left_team_won = bool(random.getrandbits(1))
                                row[2] = "defeats" if left_team_won else "loses to"
                                score_row[1 if left_team_won else 4] = int(score_row[1 if left_team_won else 4]) + 1
                                game.players[0 if left_team_won else 1].score += 1
                                game.winner = [game.players[0 if left_team_won else 1].id]
                                self.update_standings_with_game(team_standings, player_standings, team_a, game.players[0].name, game.players[0].id, tab[0:2], left_team_won)
                                self.update_standings_with_game(team_standings, player_standings, team_b, game.players[1].name, game.players[1].id, tab[0:2], not left_team_won)
                            
                            games_to_delete.append(game)
            # Add the last updated time to the sheet so people know when it is broken
            if len(tab_rows[0]) < 6:
                # Likely only 5 elements then
                tab_rows[0].append(datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
            else:
                # Overwrite previous value
                tab_rows[0][5] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            self.sheet.update_rows_raw(f"{tab}!A1:{'K' if is_2v2 else'G'}300", tab_rows)
            log_message(f"Finished updating games in {tab}. Newly finished games: {newly_finished_games_count}; games to delete: {len(games_to_delete)}", "update_new_games")
        
        with open("data/standings.json", "w", encoding="utf-8") as output_file:
            json.dump(jsonpickle.encode((team_standings, player_standings)), output_file)
        
        return newly_finished_games, games_to_delete
    
    def score_2v2_game(
            self, game: WarzoneGame, row: List[str], teams: Tuple[str, str], tab: str, score_row: List[str],
            team_standings: Dict[str, TeamResult], player_standings: Dict[str, GameResult],
            newly_finished_games: Dict[str, List[WarzoneGame]], games_to_delete: Dict[str, List[WarzoneGame]]
        ):
            newly_finished_games_count = 0
            players_by_team: Dict[str, List[WarzonePlayer]] = {teams[0]: [], teams[1]: []}
            for player in game.players:
                # Change player team from the Warzone integer into the actual team name (ex "4" -> "CAN")
                player.team = TEAM_NAME_TO_API_VALUE.inverse[player.team]
                players_by_team[player.team].append(player)
            sorted_players: List[List[WarzonePlayer]] = list(map(
                lambda e: sorted(e),
                players_by_team.values()
            ))

            # Ensure that players (by team) are in correct order of google sheets row
            if sorted_players[0][0].team != teams[0]:
                sorted_players.reverse()
            
            # Initialize the player score for the game (used for the bot if game is done)
            for lplayer in sorted_players[0]:
                lplayer.score = int(score_row[2])
            for rplayer in sorted_players[1]:
                rplayer.score = int(score_row[7])

            # Game is not finished, but we will update the progress (ie round or stage)
            while len(row) < 3+2*len(game.players):
                row.append("")
            if game.outcome == Game.Outcome.WAITING_FOR_PLAYERS:
                row[2+2*len(game.players)] = "Lobby"
            elif game.outcome == Game.Outcome.DISTRIBUTING_TERRITORIES:
                row[2+2*len(game.players)] = "Picks"
            else:
                row[2+2*len(game.players)] = f"Turn {game.round+1}"

            if game.outcome == Game.Outcome.FINISHED:
                # Game is finished, assign the defeat/loses to label
                log_message(f"New game finished with the following outcome: {game}", "update_new_games")
                newly_finished_games.setdefault(tab, []).append(game)
                newly_finished_games_count += 1
                if any(player.outcome == WarzonePlayer.Outcome.WON for player in sorted_players[0]):
                    # Left team wins
                    loser = sorted_players[1]
                    row[2*len(sorted_players[0])] = "defeats"
                    score_row[2] = int(score_row[2]) + 1
                    for player in sorted_players[0]:
                        player.score += 1
                    game.winner = [e.id for e in sorted_players[0]]
                    self.update_standings_with_2v2_game(team_standings, player_standings, sorted_players[0][0].team, sorted_players[0], tab[0:2], True)
                    self.update_standings_with_2v2_game(team_standings, player_standings, sorted_players[1][0].team, sorted_players[1], tab[0:2], False)
                elif any(player.outcome == WarzonePlayer.Outcome.WON for player in sorted_players[1]):
                    # Right team wins
                    loser = sorted_players[0]
                    row[2*len(sorted_players[0])] = "loses to"
                    score_row[2*len(sorted_players[0])+3] = int(score_row[2*len(sorted_players[0])+3]) + 1
                    for player in sorted_players[1]:
                        player.score += 1
                    game.winner = [e.id for e in sorted_players[1]]
                    self.update_standings_with_2v2_game(team_standings, player_standings, sorted_players[0][0].team, sorted_players[0], tab[0:2], False)
                    self.update_standings_with_2v2_game(team_standings, player_standings, sorted_players[1][0].team, sorted_players[1], tab[0:2], True)
                else:
                    # Randomly assign win (probably because they voted to end)
                    left_team_won = bool(random.getrandbits(1))
                    loser = sorted_players[int(left_team_won)]
                    row[2*len(sorted_players[0])] = "defeats" if left_team_won else "loses to"
                    score_row[2 if left_team_won else 2*len(sorted_players[0])+3] = int(score_row[2 if left_team_won else 2*len(sorted_players[0])+3]) + 1
                    for player in sorted_players[0 if left_team_won else 1]:
                        player.score += 1
                    game.winner = [e.id for e in sorted_players[0 if left_team_won else 1]]
                    self.update_standings_with_2v2_game(team_standings, player_standings, sorted_players[0][0].team, sorted_players[0], tab[0:2], left_team_won)
                    self.update_standings_with_2v2_game(team_standings, player_standings, sorted_players[1][0].team, sorted_players[1], tab[0:2], not left_team_won)
                if any(player.outcome == WarzonePlayer.Outcome.BOOTED for player in loser):
                    row[6] = f"Turn {game.round+1} - Booted"
            elif game.outcome == Game.Outcome.WAITING_FOR_PLAYERS and datetime.now(timezone.utc) - game.start_time > timedelta(days=4):
                # Game has been in the join lobby for too long. Game will be deleted and appropriate winner selected according to algorithm:
                # 1. Assign win to left player if they have joined, or are invited and the right player declined
                # 2. Assign win to the right player if they have joined, or are invited and the left player declined
                # 3. Randomly assign win if both players are invited, or declined
                log_message(f"New game pased join time: {', '.join(map(lambda e: e.get_player_state_str(), game.players))} -- {game.link}", "update_new_games")
                log_message(f"Storing end response: {game}")
                newly_finished_games.setdefault(tab, []).append(game)
                newly_finished_games_count += 1
                row[10] = "Deleted"
                if all(player.outcome == WarzonePlayer.Outcome.PLAYING for player in sorted_players[0]) or \
                    (all(player.outcome != WarzonePlayer.Outcome.DECLINED for player in sorted_players[0]) and any(player.outcome == WarzonePlayer.Outcome.DECLINED for player in sorted_players[1])):
                    # Left team wins
                    row[2*len(sorted_players[0])] = "defeats"
                    score_row[2] = int(score_row[2]) + 1
                    for player in sorted_players[0]:
                        player.score += 1
                    game.winner = [e.id for e in sorted_players[0]]
                    self.update_standings_with_2v2_game(team_standings, player_standings, sorted_players[0][0].team, sorted_players[0], tab[0:2], True)
                    self.update_standings_with_2v2_game(team_standings, player_standings, sorted_players[1][0].team, sorted_players[1], tab[0:2], False)
                elif all(player.outcome == WarzonePlayer.Outcome.PLAYING for player in sorted_players[1]) or \
                    (all(player.outcome != WarzonePlayer.Outcome.DECLINED for player in sorted_players[1]) and any(player.outcome == WarzonePlayer.Outcome.DECLINED for player in sorted_players[0])):
                    # Right team wins
                    row[2*len(sorted_players[0])] = "loses to"
                    score_row[2*len(sorted_players[0])+3] = int(score_row[2*len(sorted_players[0])+3]) + 1
                    for player in sorted_players[1]:
                        player.score += 1
                    game.winner = [e.id for e in sorted_players[1]]
                    self.update_standings_with_2v2_game(team_standings, player_standings, sorted_players[0][0].team, sorted_players[0], tab[0:2], False)
                    self.update_standings_with_2v2_game(team_standings, player_standings, sorted_players[1][0].team, sorted_players[1], tab[0:2], True)
                else:
                    # Some weird combo where neither player accepted
                    # Randomly assign winner
                    left_team_won = bool(random.getrandbits(1))
                    row[2*len(sorted_players[0])] = "defeats" if left_team_won else "loses to"
                    score_row[2 if left_team_won else 2*len(sorted_players[0])+3] = int(score_row[2 if left_team_won else 2*len(sorted_players[0])+3]) + 1
                    for player in sorted_players[0 if left_team_won else 1]:
                        player.score += 1
                    game.winner = [e.id for e in sorted_players[0 if left_team_won else 1]]
                    self.update_standings_with_2v2_game(team_standings, player_standings, sorted_players[0][0].team, sorted_players[0], tab[0:2], left_team_won)
                    self.update_standings_with_2v2_game(team_standings, player_standings, sorted_players[1][0].team, sorted_players[1], tab[0:2], not left_team_won)
                
                games_to_delete.append(game)
            return newly_finished_games_count
    
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
    
    def delete_unstarted_games(self, games_to_delete: List[WarzoneGame]):
        """
        Deletes a list of warzone games that have not begun yet through the WZ API.
        """
        failed_to_delete_games = []
        for game in games_to_delete:
            log_message(f"Deleting the following game: {game}", "delete_unstarted_games")
            try:
                self.api.delete_game(int(self.convert_wz_game_link_to_id(game.link)))
            except Exception as e:
                failed_to_delete_games.append(game)
                log_exception(f"Unable to delete game {game.link}:\n{e}")
    
    def update_standings_with_game(self, team_standings: Dict[str, TeamResult], player_standings: Dict[str, PlayerResult], team: str, player_name: str, player_id: int, round: str, is_won: bool):
        if is_won:
            team_standings[team].add_win(round)
            player_standings.setdefault(player_id, PlayerResult(player_name, player_id, team)).wins += 1
        else:
            team_standings[team].add_loss(round)
            player_standings.setdefault(player_id, PlayerResult(player_name, player_id, team)).losses += 1
    
    def update_standings_with_2v2_game(self, team_standings: Dict[str, TeamResult], player_standings: Dict[str, PlayerResult], team: str, players: List[WarzonePlayer], round: str, is_won: bool):
        if is_won:
            team_standings[team].add_win(round)
            for player in players:
                player_standings.setdefault(player.id, PlayerResult(player.name, player.id, team)).wins += 1
        else:
            team_standings[team].add_loss(round)
            for player in players:
                player_standings.setdefault(player.id, PlayerResult(player.name, player.id, team)).losses += 1
    
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
        
        log_message(f"Updated player stats with a total {len(current_data)} rows", "write_standings")
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
                row[3] = sum(map(lambda e: e.wins, team_standings[row[0]].games_result.values()))
                row[4] = sum(map(lambda e: e.losses, team_standings[row[0]].games_result.values()))
                team_standings.pop(row[0])
        for _, ts in team_standings.items():
            current_data.append(
                [ts.name, ts.round_wins, ts.round_losses,
                 sum(map(lambda e: e.wins, ts.games_result.values())),
                 sum(map(lambda e: e.losses, ts.games_result.values()))
                ]
            )
        
        log_message(f"Updated team stats with a total {len(current_data)} rows", "write_standings")
        self.sheet.update_rows_raw(f"Country_Stats!A1:E{len(current_data)}", current_data)
    
    def write_newly_finished_games(self, newly_finished_games: Dict[str, List[WarzoneGame]]):
        """
        Combines the existing newly_finished_games that have not been posted yet with the newly finished games from this check
        """

        if not os.path.isfile("data/newly_finished_games.json"):
            with open("data/newly_finished_games.json", "w", encoding="utf-8") as output_file:
                json.dump(jsonpickle.encode({}), output_file)
        with open ("data/newly_finished_games.json", "r", encoding="utf-8") as input_file:
            buffer_newly_finished_games = jsonpickle.decode(json.load(input_file))
            conmbined_newly_finished = { key:buffer_newly_finished_games.get(key,[])+newly_finished_games.get(key,[]) for key in set(list(buffer_newly_finished_games.keys())+list(newly_finished_games.keys())) }
        
        with open("data/newly_finished_games.json", "w", encoding="utf-8") as output_file:
            log_message("JSON version of newly finished games saved to 'newly_finished_games.json'", "write_newly_finished_games")
            json.dump(jsonpickle.encode(conmbined_newly_finished), output_file)

