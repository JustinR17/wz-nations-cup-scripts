from collections import Counter
import json
from random import shuffle

from typing import List
from NCTypes import Matchup, Player, Team
from sheet import GoogleSheet
import jsonpickle

from utils import log_message


class CreateMatches:

    def __init__(self, config):
        self.config = config
        self.sheet = GoogleSheet(config)

    def run(self, input_sheet_name: str, output_sheet_name: str, round: int):
        """
        Reads the google sheet with a list of teams. Creates matchups between countries and outputs to google sheets, a file & terminal output
        """

        teams = self.parse_sheet_for_teams(input_sheet_name)
        matchups = self.create_team_matchups(teams)
        self.write_matchups(output_sheet_name, matchups, round)


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
                current_team.players.append(Player(row[0], int(row[1]), current_team))
        return teams

    def create_team_matchups(self, teams: List[Team]) -> List[Matchup]:
        """
        Given a list of teams (where consecutive pairs face each other), create unique matchups between players.

        Returns a list of team matchups.
        """

        matchups: List[Matchup] = []
        for i in range(0, len(teams), 2):
            extended_teams = [[], []]
            for j in range(12):
                # 12 players per team, but this can vary on how many games per player depending on team size
                extended_teams[0].append(teams[i].players[j%len(teams[i].players)])
                extended_teams[1].append(teams[i+1].players[j%len(teams[i+1].players)])

            # Since we just shuffle, it is possible for the pairings to be invalid. Must check this
            iterations = 1
            shuffle(extended_teams[0])
            shuffle(extended_teams[1])
            while not self.is_valid_matchup(extended_teams[0], extended_teams[1], len(teams[i].players) == 3 and len(teams[i].players) == 3) and iterations < 1000:
                iterations += 1
                shuffle(extended_teams[0])
                shuffle(extended_teams[1])
            matchups.append(Matchup(teams[i], teams[i+1]))
            matchups[-1].import_games_from_pairing_lists(extended_teams)
            
            log_message(f"{teams[i].name} vs. {teams[i+1].name} ({iterations} iterations)", "create_team_matchups")
            for game in matchups[-1].games:
                log_message(f"\t{game.players[0].name.encode()} vs. {game.players[1].name.encode()}", "create_team_matchups")
            log_message("", "create_team_matchups")
        return matchups

    def is_valid_matchup(self, team_a: List[Player], team_b: List[Player], minimum_teams: bool) -> bool:
        """
        Check if a shuffled list of teams is valid (ie. no two players face each other more than once).

        Returns true if the matchup is valid.
        """
        seen_matches = []


        for i in range(12):
            seen_matches.append((team_a[i].id, team_b[i].id))
        
        return Counter(seen_matches).most_common(1)[0][1] <= (2 if minimum_teams else 1)

    def write_matchups(self, sheet_name: str, matchups: List[Matchup], round: str):
        """
        Output the matchups to a file for safety and to the google sheets
        """

        # Output to file first since this is safer
        with open(f"data/matchups_output_r{round}.json", "w", encoding="utf-8") as output_file:
            log_message("JSON version of matchups data is stored to 'matchups_output.json'", "write_matchups")
            json.dump(jsonpickle.encode(matchups), output_file)

        sheet_data: List[List[str]] = [[]]
        for matchup in matchups:
            sheet_data.append([matchup.teams[0].name, len(matchup.teams[0].players)-6, "vs.", matchup.teams[1].name, len(matchup.teams[1].players)-6])
            for game in matchup.games:
                sheet_data.append([game.players[0].name, game.players[0].id, "", game.players[1].name, game.players[1].id, game.link])
            sheet_data.append([]) # Empty row to divide teams
        self.sheet.update_rows_raw(f"{sheet_name}!A1:F{len(sheet_data)}", sheet_data)
        log_message(f"Updated google sheets with {len(sheet_data)} new rows", "write_matchups")

