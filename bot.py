import os
from typing import Any, Dict, List
import discord
import json
from discord.ext import commands
import jsonpickle
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from discord import app_commands

from NCTypes import PlayerResult, TeamResult, WarzoneGame
from utils import log_exception, log_message

intents = discord.Intents.default()
intents.members = True
intents.messages = True
intents.message_content = True
client = discord.Client(intents=intents)


ROUND_TO_TEMPLATE = {
    "R1": "Phobia",
    "R2": "Yorkshire Brawl",
    "R3": "Malvia",
    "R4": "Laketown",
    "R5": "Volcano 2v2",
}

ROUND_TO_COLOUR = {
    "R1": discord.Colour.blurple(),
    "R2": discord.Colour.blue(),
    "R3": discord.Colour.green(),
    "R4": discord.Colour.yellow(),
    "R5": discord.Colour.red(),
}

class NCComands(commands.Cog):

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
    
    @app_commands.command(name="pstats", description="returns a player's statistics")
    @app_commands.describe(player_id="the player ID to search for")
    async def pstats(self, interaction: discord.Interaction, player_id: str):
        team_standings: Dict[str, TeamResult] = {}
        player_standings: Dict[str, PlayerResult] = {}
        if not os.path.isfile("data/standings.json"):
            await interaction.response.send_message("No standings file exists yet")
            return
        with open("data/standings.json", "r", encoding="utf-8") as input_file:
            team_standings, player_standings = jsonpickle.decode(json.load(input_file))
        
        if player_id in player_standings:
            await interaction.response.send_message(f"**{player_standings[player_id].name}** ({player_standings[player_id].team}): {player_standings[player_id].wins}-{player_standings[player_id].losses}")
        else:
            await interaction.response.send_message(f"Unable to find player with ID '{player_id}'")
    
    @app_commands.command(name="pnstats", description="returns a player's statistics by name")
    @app_commands.describe(player_name="the player name to search for")
    async def pnstats(self, interaction: discord.Interaction, player_name: str):
        team_standings: Dict[str, TeamResult] = {}
        player_standings: Dict[str, PlayerResult] = {}
        if not os.path.isfile("data/standings.json"):
            await interaction.response.send_message("No standings file exists yet")
            return
        with open("data/standings.json", "r", encoding="utf-8") as input_file:
            team_standings, player_standings = jsonpickle.decode(json.load(input_file))
        
        found_matches: List[PlayerResult] = []
        for _, player in player_standings.items():
            if player_name.lower() in player.name.lower():
                found_matches.append(player)
        if len(found_matches) > 1:
            player_str = "\n\t".join(
                map(
                    lambda e: f"**{e.name}** ({e.team}): {e.wins}-{e.losses}", found_matches
                )
            )
            output_str = f"{len(found_matches)} matches found:\n\t{player_str}"
            await interaction.response.send_message(output_str)
        elif len(found_matches) == 1:
            await interaction.response.send_message(f"**{found_matches[0].name}** ({found_matches[0].team}): {found_matches[0].wins}-{found_matches[0].losses}")
        else:
            await interaction.response.send_message(f"Unable to find player with name '{player_name}'")
    
    @app_commands.command(name="cstats", description="returns a country's statistics")
    @app_commands.describe(country_name="the country name to search for")
    async def cstats(self, interaction: discord.Interaction, country_name: str):
        team_standings: Dict[str, TeamResult] = {}
        player_standings: Dict[str, PlayerResult] = {}
        if not os.path.isfile("data/standings.json"):
            await interaction.response.send_message("No standings file exists yet")
            return
        with open("data/standings.json", "r", encoding="utf-8") as input_file:
            team_standings, player_standings = jsonpickle.decode(json.load(input_file))
        
        if country_name in team_standings:
            output_str = f"**{team_standings[country_name].name}**: {team_standings[country_name].round_wins} round wins, {team_standings[country_name].round_losses} round losses\n"
            for round, gr in team_standings[country_name].games_result.items():
                output_str += f"\t{round} vs {gr.opp}: {gr.pts_for}-{gr.pts_against} ({gr.wins} wins, {gr.losses} losses)\n"
            await interaction.response.send_message(output_str)
        else:
            await interaction.response.send_message(f"Unable to find country with name '{country_name}'")
    
    @app_commands.command(name="link", description="returns the google sheets link")
    async def link(self, interaction: discord.Interaction):
        await interaction.response.send_message("<https://docs.google.com/spreadsheets/d/1QPKGgwToBd2prap8u3XVUx9F47SuvMH9wJruvG0t2D4/edit#gid=1668893548>")
    
    @app_commands.command(name="kill", description="justin only command")
    async def kill(self, interaction: discord.Interaction):
        if interaction.user.id == 162968893177069568:
            await interaction.response.send_message("Killing the bot")
            await self.bot.close()
        else:
            await interaction.response.send_message("Only Justin can use this command")
            await self.bot.close()
    
    @commands.command(name="sync") 
    async def sync(self, ctx):
        synced = await self.bot.tree.sync()
        print(f"Synced {len(synced)} command(s).")
        await ctx.send(f"Synced {len(synced)} command(s).")

class NationsCupBot(commands.Bot):

    def __init__(self, *, config: Dict, **options: Any) -> None:
        super().__init__(command_prefix="nc!", intents=intents, **options)
        self.config = config
        self.jobs_scheduled = False


    async def post_game_updates_job(self):
        """
        Read the buffer newly finished game file and post games to discord. Clears the buffer file after completion.
        """

        # Post the games that have finished since the last time we checked
        log_message("Running post_game_updates_job", "bot")
        with open (f"data/newly_finished_games.json", "r", encoding="utf-8") as input_file:
            buffer_newly_finished_games: Dict[str, List[WarzoneGame]] = jsonpickle.decode(json.load(input_file))
            
            discord_channel = self.get_channel(int(self.config["game_log_channel"]))
            successfully_posted, total = 0, 0
            for round, games in buffer_newly_finished_games.items():
                for game in games:
                    total += 1
                    try:
                        if game.winner == game.players[0].id:
                            winner_name, winner_team = game.players[0].name, game.players[0].team
                            loser_name = game.players[1].name
                        else:
                            winner_name, winner_team = game.players[1].name, game.players[1].team
                            loser_name = game.players[0].name
                        embed = discord.Embed(
                            title=f"{winner_name} defeats {loser_name}"[0:256],
                            description=f"[Game Link]({game.link})"[0:4096],
                            colour=ROUND_TO_COLOUR[round[0:2]]
                        )
                        embed.add_field(name=f"{round[0:2]} {ROUND_TO_TEMPLATE[round[0:2]]}"[0:256], value=f"**{winner_team}** won"[0:1024])
                        embed.set_footer(text=f"{game.players[0].team} {game.players[0].score} - {game.players[1].team} {game.players[1].score}"[0:2048])
                        await discord_channel.send(embed=embed)
                        successfully_posted += 1
                    except Exception as e:
                        log_exception(f"Error while handling game {game.link}: {e}")
        log_message(f"Successfully outputted {successfully_posted} of {total} game updates", "bot")
            
        if successfully_posted:
            with open (f"data/newly_finished_games.json", "w", encoding="utf-8") as output_file:
                # Reset the buffer file
                log_message("Resetting the buffer file after posting game updates", "bot")
                json.dump(jsonpickle.encode({}), output_file)

    async def on_ready(self):
        await self.add_cog(NCComands(self))
        # Start schedulers (only on first run)
        if not self.jobs_scheduled:
            log_message("Scheduled post_game_updates_job", "bot")
            scheduler = AsyncIOScheduler()
            scheduler.add_job(self.post_game_updates_job, CronTrigger(hour="*", minute="10", second="0"))
            scheduler.start()
            self.jobs_scheduled = True
