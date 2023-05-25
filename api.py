

# https://www.warzone.com/wiki/Category:API
from typing import List, Tuple
import requests

class GameResult:
    def __init__(self) -> None:
        pass

class API:

    CREATE_GAME_ENDPOINT = "https://www.warzone.com/API/CreateGame"
    DELETE_GAME_ENDPOINT = "https://www.warzone.com/API/DeleteLobbyGame"
    QUERY_GAME_ENDPOINT = "https://www.warzone.com/API/GameFeed?GameID="
    VALIDATE_INVITE_TOKEN_ENDPOINT = "https://www.warzone.com/API/ValidateInviteToken?Token="

    def __init__(self, config):
        self.config = config
    
    def check_game(self, game_id: str) -> GameResult:
        """
        Checks the progress and results of a game using the WZ API.

        Returns the result of the game (in-progress or completed).
        """
        pass
    
    def create_game(self, players, template, name: str, description: str) -> str | None:
        """
        Creates a game using the WZ API with the specified players, template, and game name/description.

        Returns the game ID if successfully created, else None.
        """
        pass

    def validate_player_template_access(self, player_id: str, templates: List) -> Tuple[bool, List[bool]]:
        """
        Checks if the player has access to the list of templates.

        Returns a tuple containing (True if player has access to all templates, List of booleans on access for each template).
        """
        pass
