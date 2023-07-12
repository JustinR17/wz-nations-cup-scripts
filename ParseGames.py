from datetime import datetime, timedelta, timezone
import json
import os
from typing import Dict, List, Tuple

import jsonpickle
from NCTypes import Game, WarzoneGame, WarzonePlayer
from api import API
from sheet import GoogleSheet
import re


class ParseGames:

    def __init__(self, config):
        self.config = config
        self.sheet = GoogleSheet(config)
        self.api = API(config)
    
    def run(self):
        """
        Reads the google sheets games and updates finished games. Newly finished games are stored in a buffer file for the discord bot to read
        """
        newly_finished_games, games_to_delete = self.update_new_games()
        self.delete_unstarted_games(games_to_delete)
        self.write_newly_finished_games(newly_finished_games)

    
    def update_new_games(self) -> Tuple[Dict[str, List[WarzoneGame]], List[WarzoneGame]]:
        """
        Checks all game tabs for games that have newly finished. Writes the new results in the tab.

        Returns a dictionary of lists (tab name -> List[Games])
        """
        
        newly_finished_games: Dict[str, List[WarzoneGame]] = {}
        games_to_delete = []
        for tab in self.get_game_tabs():
            tab_rows = self.sheet.get_rows(f"{tab}!A1:F300")

            team_a, team_b, score_row = "", "", []
            for row in tab_rows:
                if not row:
                    # Finished the previous matchup
                    team_a, team_b, score_row = "", "", []
                else:
                    if not team_a and not team_b:
                        # New teams to add
                        team_a, team_b, score_row = row[0], row[3], row
                    elif not row[2]:
                        # Game to check
                        game = self.api.check_game(self.convert_wz_game_link_to_id(row[5]))
                        if game.players[0].id != row[1]:
                            game.players.reverse()
                        game.players[0].team, game.players[1].team = team_a,  team_b

                        print(game.start_time)
                        print(datetime.now())
                        if game.outcome == Game.Outcome.FINISHED:
                            # TODO check these game outcomes
                            newly_finished_games.setdefault(tab, []).append(game)
                            if game.players[0].outcome == WarzonePlayer.Outcome.WON and game.players[0].id == row[1]:
                                # Left team wins
                                row[2] = "defeats"
                                score_row[1] = int(score_row[1]) + 1
                            else:
                                row[2] = "loses to"
                                score_row[4] = int(score_row[4]) + 1
                        elif game.outcome == Game.Outcome.WAITING_FOR_PLAYERS and datetime.now(timezone.utc) - game.start_time > timedelta(minutes=4):
                            newly_finished_games.setdefault(tab, []).append(game)
                            if (game.players[0].outcome == WarzonePlayer.Outcome.INVITED or game.players[0].outcome == WarzonePlayer.Outcome.DECLINED) \
                                and game.players[0].id == row[1]:
                                # Left team loses
                                row[2] = "loses to"
                                score_row[4] = int(score_row[4]) + 1
                            else:
                                row[2] = "defeats"
                                score_row[1] = int(score_row[1]) + 1
                            games_to_delete.append(game)
            self.sheet.update_rows_raw(f"{tab}!A1:F300", tab_rows)
        return newly_finished_games, games_to_delete
    
    def get_game_tabs(self) -> List[str]:
        """
        Returns a list of the google sheets tabs containing games.
        """
        game_tabs = []
        sheets = self.sheet.get_sheet_tabs_data()
        for tab in sheets:
            # Get the tabs that we should parse
            if re.search("^R\d Games$", tab["properties"]["title"]):
                game_tabs.append(tab["properties"]["title"])
        return game_tabs

    def convert_wz_game_link_to_id(self, game_link: str):
        return game_link[43:]
    
    def delete_unstarted_games(self, games_to_delete: List[WarzoneGame]):
        """
        Deletes a list of warzone games that have not begun yet through the WZ API.
        """
        for game in games_to_delete:
            print(f"Deleting the {game.players[0].team} v {game.players[1].team} game between {game.players[0].name} ({game.players[0].id}) & {game.players[1].name} ({game.players[1].id})".encode())
            self.api.delete_game(int(self.convert_wz_game_link_to_id(game.link)))
    
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
            print("JSON version of newly finished games saved to 'newly_finished_games.json'")
            json.dump(jsonpickle.encode(conmbined_newly_finished), output_file)

