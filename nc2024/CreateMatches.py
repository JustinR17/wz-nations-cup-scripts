from collections import Counter
from random import shuffle

from typing import Dict, List
from NCTypes import Matchup, Player, Team
from sheet import GoogleSheet

from utils import log_exception, log_message


class CreateMatches:

    def __init__(self, config):
        self.config = config
        self.dryrun = "dryrun" in config and config["dryrun"]
        self.sheet = GoogleSheet(config)

    def run(self, input_sheet_name: str, output_sheet_name: str):
        """
        Reads the google sheet with a list of teams. Creates matchups between countries and outputs to google sheets, a file & terminal output
        """
        try:
            log_message("Running CreateMatches", "CreateMatches.run")
            teams = self.parse_sheet_for_teams(input_sheet_name)
            
            # Did not want to mix up the flows too much so separated 1v1s and 2v2s
            log_message("Running 1v1 matchup creation", "CreateMatches.run")
            matchups = self.create_team_matchups(teams)
            self.write_matchups(output_sheet_name, matchups)
        except Exception as e:
            log_exception(e)


    def parse_sheet_for_teams(self, sheet_name) -> List[Team]:
        teams: List[Team] = []
        sheet_rows = self.sheet.get_rows(f"{sheet_name}!A1:B300")

        current_team: Team | None = None
        for row in sheet_rows:
            if not row:
                # Empty row (denotes the end of a team)
                current_team = None
            elif not current_team and row:
                # New team to add
                current_team = Team(row[0].strip())
                teams.append(current_team)
            elif row:
                # New player to add to team (need to regex capture the ID since warzone URLs are provided)
                if current_team:
                    # current_team.players.append(Player(row[0].strip(), int(re.search(r'^.*?p=(\d*).*$', row[1]).group(1)), current_team)) # type: ignore
                    current_team.players.append(Player(row[0].strip(), row[1], current_team))
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
            while not self.is_valid_matchup(extended_teams[0], extended_teams[1], len(teams[i].players) == 3 and len(teams[i+1].players) == 3) and iterations < 1000:
                iterations += 1
                shuffle(extended_teams[0])
                shuffle(extended_teams[1])
            
            if iterations == 1000:
                # This should not happen if the matchup was added correctly
                log_exception(f"Reached 1000 iterations while finding matchups for {teams[i].name} vs {teams[i+1].name}")
            
            matchups.append(Matchup(teams[i], teams[i+1]))
            matchups[-1].import_games_from_pairing_lists(extended_teams)
            
            log_message(f"{teams[i].name} vs. {teams[i+1].name} ({iterations} iterations)", "create_team_matchups")
            for game in matchups[-1].games:
                log_message(f"\t{game.players[0].name.encode()} vs. {game.players[1].name.encode()}", "create_team_matchups")
            log_message("", "create_team_matchups")
        return matchups

    def is_valid_matchup(self, team_a: List[Player], team_b: List[Player], minimum_teams: bool) -> bool:
        """
        Check if a shuffled list of teams is valid. This varies if both team has 3 players vs not.

        1. If both teams have 3 players (denoted by minimum_teams), then each player will have a duplicate game agaisnt 1 opponent only.
        2. If not, then not player should have a duplicate game against an opponent.

        Returns true if the matchup is valid.
        """
        seen_matches: Dict[str, List[str]] = {}


        for i in range(12):
            seen_matches.setdefault(team_a[i].id, []).append(team_b[i].id)
            seen_matches.setdefault(team_b[i].id, []).append(team_a[i].id)
        
        # Only when both teams have 3 should players get a duplicate game
        # Each player should only get one game that is duplicate (ie. cannot face only two people twice)
        for opps in seen_matches.values():
            # Only when both teams have 3 should players get a duplicate game
            # Each player should only get one game that is duplicate (ie. cannot face only two people twice)
            most_seen_matches = Counter(opps).most_common(2)
            if len(most_seen_matches) < 2 or most_seen_matches[0][1] > (2 if minimum_teams else 1) or most_seen_matches[1][1] > 1:
                return False
        
        return True

    def write_matchups(self, sheet_name: str, matchups: List[Matchup]):
        """
        Output the matchups to a file for safety and to the google sheets
        """

        sheet_data: List[List[str]] = []
        for matchup in matchups:
            sheet_data.append([matchup.teams[0].name, "0", "vs.", matchup.teams[1].name, "0"])
            for game in matchup.games:
                sheet_data.append([game.players[0].name, game.players[0].id, "", game.players[1].name, game.players[1].id, game.link])
            sheet_data.append([]) # Empty row to divide teams
        # TODO: confirm before runnings
        self.sheet.update_rows_raw(f"{sheet_name}!K3:P{len(sheet_data)+3}", sheet_data)
        log_message(f"Updated google sheets with {len(sheet_data)} new rows", "write_matchups")

