from datetime import datetime
import re

from api import API
from sheet import GoogleSheet

from utils import log_exception, log_message


class ValidatePlayers:

    def __init__(self, config):
        self.config = config
        self.sheet = GoogleSheet(config)
        self.api = API(config)

    def run(self):
        """
        Reads the google sheets games and updates finished games. Newly finished games are stored in a buffer file for the discord bot to read
        """
        log_message("Running ValidatePlayers", "ValidatePlayers.run")
        self.validate_players_on_templates()

    def validate_players_on_templates(self):
        sheet_rows = self.sheet.get_rows("Rosters!C3:L300")
        status_cells = self.sheet.get_rows("Rosters!D1:E1")
        templates = []

        for i, row in enumerate(sheet_rows):
            if i == 0:
                # first header row, parse templates
                for col in row[4:]:
                    templates.append(
                        re.search(r"^.*TemplateID=(\d*)$", col.strip()).group(1)
                    )
            elif not row:
                # Empty row (denotes the end of a team)
                print()
            elif row:
                # New player to check
                if row[0]:
                    print(f"Checking new team: {row[0].strip()}")
                row.extend("" for _ in range(10 - len(row)))
                try:
                    validate_response = self.api.validate_player_template_access(
                        int(re.search(r"^.*?p=(\d*).*$", row[2]).group(1)), templates
                    )

                    if not validate_response[0]:
                        print(
                            f"\t❌  {row[1].encode()} ({row[2]}) - Likely blacklisted"
                        )
                        for i in range(7):
                            row[i + 4] = "❌"
                    elif validate_response[1]:
                        print(f"\t✅ {row[1].encode()} ({row[2]})")
                    else:
                        invalid_templates = []
                        for i, valid in enumerate(validate_response[2]):
                            if valid:
                                row[i + 4] = "✅"
                            else:
                                invalid_templates.append(templates[i])
                                row[i + 4] = "❌"
                        print(
                            f"\t❌  {row[1].encode()} ({row[2]}) - Invalid: {', '.join(invalid_templates)}"
                        )
                    for i, valid in enumerate(validate_response[2]):
                        if valid:
                            row[i + 4] = "✅"
                        else:
                            row[i + 4] = "❌"
                except Exception as e:
                    log_exception(
                        f"Error while handling {row[1].encode()} ({row[2]})\n{e}"
                    )
        self.sheet.update_rows_raw("Rosters!C3:L300", sheet_rows)
        status_cells[0][1] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.sheet.update_rows_raw("Rosters!D1:E1", status_cells)
