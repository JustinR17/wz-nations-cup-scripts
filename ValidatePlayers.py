import re
from typing import List

from NCTypes import Player, Team
from api import API
from sheet import GoogleSheet

from utils import log_exception, log_message


class ValidatePlayers:

    def __init__(self, config):
        self.config = config
        self.sheet = GoogleSheet(config)
        self.api = API(config)
    
    def run(self, templates: List[str], sheet: str):
        """
        Reads the google sheets games and updates finished games. Newly finished games are stored in a buffer file for the discord bot to read
        """
        log_message("Running ParseGames", "ParseGames.run")
        teams_to_validate = self.parse_sheet_for_teams(sheet)
        self.validate_players_on_template(teams_to_validate, templates)
    
    def parse_sheet_for_teams(self, sheet_name) -> List[Team]:
        teams: List[Team] = []
        sheet_rows = self.sheet.get_rows(f"{sheet_name}!A1:B200")

        current_team = None
        for row in sheet_rows:
            if not row:
                # Empty row (denotes the end of a team)
                current_team = None
            elif not current_team and row:
                # New team to add
                current_team = Team(row[0])
                teams.append(current_team)
            elif row:
                # New player to add to team
                current_team.players.append(Player(row[0], int(re.search(r'^.*?p=(\d*).*$', row[1]).group(1)), current_team))
        return teams

    def validate_players_on_template(self, teams: List[Team], templates: List[str]):
        for team in teams:
            print(f"Validating players for team {team.name}")
            for player in team.players:
                try:
                    validate_response = self.api.validate_player_template_access(player.id, templates)

                    if not validate_response[0]:
                        print(f"\t✖  {player.name.encode()} ({player.id}) - Likely blacklisted")
                    elif validate_response[1]:
                        print(f"\t✅ {player.name.encode()} ({player.id})")
                    else:
                        invalid_templates = []
                        for i, valid in enumerate(validate_response[2]):
                            if not valid:
                                invalid_templates.append(templates[i])
                        print(f"\t✖  {player.name.encode()} ({player.id}) - Invalid: {', '.join(invalid_templates)}")
                except Exception as e:
                    log_exception(f"Error while handling {player.name.encode()} ({player.id})\n{e}")
            print()
