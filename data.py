TAB_TO_GAME_RANGE_MAPPING = {
    "_Finals": "K2:S105",
    "_Main": "J3:R97",
    "_Qualifiers": "J3:R217",
}

# Used for PGames when we parse the team tables (used for team standings)
TAB_TO_TABLE_RANGE_MAPPING = {
    "_Finals": "B3:H17",
    "_Main": "B3:H36",
    "_Qualifiers": "B3:H42",
}

# Used for CGAMES and PGames where we don't want to update tables
CGAMES_TAB_TO_TABLE_RANGE_MAPPING = {
    "_Finals": None,
    "_Main": "B3:H36",
    "_Qualifiers": "B3:H42",
}

UNKNOWN_PLAYER_NAME = "<no player>"
NO_GAME_PLAYED = "<>"
