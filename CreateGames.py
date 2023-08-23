

import json
from typing import List
from NCTypes import Matchup
from api import API
from sheet import GoogleSheet
import jsonpickle

from utils import log_exception, log_message


class CreateGames:

    def __init__(self, config):
        self.config = config
        self.sheet = GoogleSheet(config)
        self.api = API(config)
    
    def run(self, sheet_name: str, round: str, template: str, players: int):
        """
        Reads the sheet_name matchups and creates games. The sheet will be updated with the game links
        """
        try:
            log_message("Running CreateGames", "CreateGames.run")
            matchups = self.parse_sheet_matchups(round)
            matchups = self.create_games(matchups, round, template)
            self.write_games(sheet_name, matchups, round)
        except Exception as e:
            log_exception(e)

    def parse_sheet_matchups(self, round):
        with open(f"data/matchups_output_r{round}.json", "r", encoding="utf-8") as json_file:
            json_data = jsonpickle.decode(json.load(json_file))
        
        return json_data
    
    def create_games(self, matchups: List[Matchup], round: int, template: str) -> List[Matchup]:
        for matchup in matchups:
            log_message(f"Beginning game creation for {matchup.teams[0].name} vs. {matchup.teams[1].name}", "create_games")

            for game in matchup.games:

                title = f"Nations' Cup 2023 R{round} {matchup.teams[0].name} vs. {matchup.teams[1].name}"
                description = f"""This game is a part of the Nations' Cup R{round}, run by Marcus. You have 3 days to join the game.
                
Match is between:
\t{game.players[0].name.encode()} in {matchup.teams[0].name}
\t{game.players[1].name.encode()} in {matchup.teams[1].name}

https://docs.google.com/spreadsheets/d/1QPKGgwToBd2prap8u3XVUx9F47SuvMH9wJruvG0t2D4
"""
                
                try:
                    game_link = self.api.create_game([(game.players[0].id,matchup.teams[0].name) , (game.players[1].id,matchup.teams[1].name)], template, title, description)

                    if game_link:
                        log_message(f"\tGame created between {game.players[0].name.encode()} & {game.players[1].name.encode()} - {game_link}", "create_games")
                        game.link = game_link
                except API.GameCreationException as e:
                    log_exception(f"\tGameCreationException: Unable to create game between {game.players[0].name.encode()} & {game.players[1].name.encode()}: '{str(e)}'")
                except Exception as e:
                    log_exception(f"\tUnknown Exception: Unable to create game between {game.players[0].name.encode()} & {game.players[1].name.encode()}: '{str(e)}'")
        
        return matchups

    def write_games(self, sheet_name: str, matchups: List[Matchup], round: str):
        """
        Output the matchups to a file for safety and to the google sheets
        """

        # Output to file first since this is safer
        with open(f"data/games_output_r{round}.json", "w", encoding="utf-8") as output_file:
            log_message("JSON version of matchups data is stored to 'matchups_output.json'", "write_games")
            json.dump(jsonpickle.encode(matchups), output_file)

        sheet_data: List[List[str]] = []
        for matchup in matchups:
            sheet_data.append([matchup.teams[0], 0, "vs.", matchup.teams[1], 0])
            for game in matchup.games:
                sheet_data.append([game.players[0].name, game.players[0].id, "", game.players[0].name, game.players[0].id, game.link])
            sheet_data.append([]) # Empty row to divide teams
        
        # Updating the sheet involves matching the matchups object to the sheet rows
        sheet_data = self.sheet.get_rows(f"{sheet_name}!A1:F{len(sheet_data)}")
        updated_game_links = []

        current_matchup = None
        for row in sheet_data:
            if not row:
                current_matchup = None
                updated_game_links.append([""])
            elif row and not current_matchup:
                # New matchup
                for matchup in matchups:
                    if row[0].strip() == matchup.teams[0].name or row[0].strip() == matchup.teams[1].name:
                        current_matchup = matchup
                updated_game_links.append([""])
            elif row:
                # New game link to add
                has_added_game = False
                for game in current_matchup.games:
                    if int(row[1].strip()) == game.players[0].id and int(row[4].strip()) == game.players[1].id or int(row[1].strip()) == game.players[1].id and int(row[4].strip()) == game.players[0].id:
                        updated_game_links.append([f"{API.GAME_URL}{game.link}"])
                        # Need to remove games in case there are scenarios where two players get matched up twice (ie. 3 players per team)
                        current_matchup.games.remove(game)
                        has_added_game = True
                        break
                if not has_added_game:
                    updated_game_links.append([""])
        self.sheet.update_rows_raw(f"{sheet_name}!F1:F{len(updated_game_links)}", updated_game_links)
        log_message(f"Updated the google sheet with {len(updated_game_links)} new links", "write_games")



