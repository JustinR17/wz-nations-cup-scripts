# https://www.warzone.com/wiki/Category:API
from typing import List, Tuple
import requests

from NCTypes import Game


class API:
    CREATE_GAME_ENDPOINT = "https://www.warzone.com/API/CreateGame"
    DELETE_GAME_ENDPOINT = "https://www.warzone.com/API/DeleteLobbyGame"
    QUERY_GAME_ENDPOINT = "https://www.warzone.com/API/GameFeed"
    VALIDATE_INVITE_TOKEN_ENDPOINT = (
        "https://www.warzone.com/API/ValidateInviteToken"
    )

    class GameCreationException(Exception):
        pass


    def __init__(self, config):
        self.config = config

    def check_game(self, game_id: str) -> Game:
        """
        Checks the progress and results of a game using the WZ API.

        Returns the result of the game (in-progress or completed).
        """
        game_json = requests.post(
            f"{API.QUERY_GAME_ENDPOINT}?GameID={game_id}",
            {"Email": self.config["email"], "APIToken": self.config["token"]},
        ).json()

        # game_result = GameResult(GameResult.Outcome[game_json["state"]])

    def create_game(self, players: List[str], template: str, name: str, description: str) -> str | None:
        """
        Creates a game using the WZ API with the specified players, template, and game name/description.

        Returns the game ID if successfully created, else None.
        """
        pass

    def validate_player_template_access(
        self, player_id: str, templates: List[str]
    ) -> Tuple[bool, List[bool]]:
        """
        Checks if the player has access to the list of templates.

        Returns a tuple containing (True if player has access to all templates, List of booleans on access for each template).
        """
        validate_response = requests.post(
            f"{API.VALIDATE_INVITE_TOKEN_ENDPOINT}?Token={player_id}&TemplateIDs={','.join(templates)}",
            {"Email": self.config["email"], "APIToken": self.config["token"]},
        ).json()

        has_acces_to_all_templates = True
        template_access = []
        for template in templates:
            has_acces_to_all_templates = has_acces_to_all_templates and "CanUseTemplate" in validate_response[f"template{template}"]["result"]
            template_access.append("CanUseTemplate" in validate_response[f"template{template}"]["result"])
        
        return has_acces_to_all_templates, template_access
