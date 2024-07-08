import os
from time import sleep
from typing import Any, Dict, List
import discord
import json
from discord.ext import commands
import jsonpickle
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from discord import app_commands
import os

from NCTypes import PlayerResult, TeamResult, WarzoneGame
from utils import log_exception, log_message

intents = discord.Intents.default()
intents.members = True
intents.messages = True
intents.message_content = True
client = discord.Client(intents=intents)


ROUND_TO_TEMPLATE = {
    "Qualifiers R1": "Guiroma",
    "Qualifiers R2": "French Brawl",
    "Main R1": "Strategic MME",
    "Main R2": "Africa Ultima",
    "Main R3": "Numenor",
    "Main R4": "Volcano Island",
    "Main R5": "Biomes",
}

# Reverse ROY G BIV; Finals is all gold
ROUND_TO_COLOUR = {
    "Qualifiers R1": discord.Colour.from_rgb(148, 9, 211),
    "Qualifiers R2": discord.Colour.from_rgb(75, 0, 130),
    "Main R1": discord.Colour.from_rgb(0, 0, 255),
    "Main R2": discord.Colour.from_rgb(0, 255, 0),
    "Main R3": discord.Colour.from_rgb(255, 255, 0),
    "Main R4": discord.Colour.from_rgb(255, 127, 0),
    "Main R5": discord.Colour.from_rgb(255, 0, 0),
    "Finals": discord.Colour.gold(),
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
            await interaction.response.send_message(
                f"**{player_standings[player_id].name}** ({player_standings[player_id].team}): {player_standings[player_id].wins}-{player_standings[player_id].losses}"
            )
        else:
            await interaction.response.send_message(
                f"Unable to find player with ID '{player_id}'"
            )

    @app_commands.command(
        name="pnstats", description="returns a player's statistics by name"
    )
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
                    lambda e: f"**{e.name}** ({e.team}): {e.wins}-{e.losses}",
                    found_matches,
                )
            )
            output_str = f"{len(found_matches)} matches found:\n\t{player_str}"
            await interaction.response.send_message(output_str)
        elif len(found_matches) == 1:
            await interaction.response.send_message(
                f"**{found_matches[0].name}** ({found_matches[0].team}): {found_matches[0].wins}-{found_matches[0].losses}"
            )
        else:
            await interaction.response.send_message(
                f"Unable to find player with name '{player_name}'"
            )

    @app_commands.command(name="link", description="returns the google sheets link")
    async def link(self, interaction: discord.Interaction):
        await interaction.response.send_message(
            "<https://docs.google.com/spreadsheets/d/1R7VDKXYN3ofo5xBkPQ_XOmcCCmb1W2w_kHXCO2qy_Xs>"
        )

    @app_commands.command(name="kill", description="justin only command")
    async def kill(self, interaction: discord.Interaction):
        if interaction.user.id == 162968893177069568 or interaction.user.id == 281740561885691904: # my id + rento
            await interaction.response.send_message("Killing the bot")
            os.system("sudo shutdown -h now")
        else:
            await interaction.response.send_message("Only Justin can use this command")

    @commands.command(name="sync")
    async def sync(self, ctx):
        synced = await self.bot.tree.sync()
        print(f"Synced {len(synced)} command(s).")
        await ctx.send(f"Synced {len(synced)} command(s).")

    @commands.command(name="reboot")
    async def reboot(self, ctx):
        await ctx.send("Restarting rpi")
        os.system("sudo shutdown -r now")

    @commands.command(name="msg")
    async def msg(self, ctx: commands.Context, channel: str, *msg):
        if ctx.author.id == 162968893177069568:
            dc = self.bot.get_channel(int(channel))
            await dc.send(" ".join(msg))


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
        with open(
            f"data/newly_finished_games.json", "r", encoding="utf-8"
        ) as input_file:
            buffer_newly_finished_games: Dict[str, List[WarzoneGame]] = (
                jsonpickle.decode(json.load(input_file))
            )

            discord_channel = self.get_channel(int(self.config["game_log_channel"]))
            successfully_posted, total = 0, 0
            for key, games in buffer_newly_finished_games.items():
                print(f"{len(games)} games in {key} to post")
                round, group = key.split("-")
                for game in games:
                    total += 1
                    try:
                        winners = [x for x in game.players if x.id in game.winner]
                        losers = [x for x in game.players if x.id not in game.winner]
                        log_message(f"GAME: {game}", "post_game_updates_job")
                        print(winners)
                        print(losers)
                        embed = discord.Embed(
                            title=f"{', '.join([p.name for p in winners])} defeats {', '.join([p.name for p in losers])}"[
                                0:256
                            ],
                            description=f"[Game Link]({game.link})"[0:4096],
                            colour=ROUND_TO_COLOUR[round],
                        )
                        embed.add_field(
                            name=f"{round} {ROUND_TO_TEMPLATE[round]} - {group}"[0:256],
                            value=f"**{winners[0].team}** won"[0:1024],
                        )
                        embed.set_footer(
                            text=f"{winners[0].team} {winners[0].score:g} - {losers[0].team} {losers[0].score:g}"[
                                0:2048
                            ]
                        )
                        sent_embed = await discord_channel.send(embed=embed)

                        if "CAN" in winners[0].team:
                            await sent_embed.add_reaction("🇨🇦")
                            await sent_embed.add_reaction("🎉")
                            # await sent_embed.add_reaction("🇨")
                            # await sent_embed.add_reaction("🇦")
                            # await sent_embed.add_reaction("🇳")
                            # await sent_embed.add_reaction("🍁")
                            # await sent_embed.add_reaction("🦫")
                        successfully_posted += 1
                    except Exception as e:
                        log_exception(f"Error while handling game {game.link}: {e}")
        log_message(
            f"Successfully outputted {successfully_posted} of {total} game updates",
            "bot",
        )

        if successfully_posted:
            with open(
                f"data/newly_finished_games.json", "w", encoding="utf-8"
            ) as output_file:
                # Reset the buffer file
                log_message(
                    "Resetting the buffer file after posting game updates", "bot"
                )
                json.dump(jsonpickle.encode({}), output_file)

    async def on_ready(self):
        await self.add_cog(NCComands(self))
        # Start schedulers (only on first run)
        if not self.jobs_scheduled:
            log_message("Scheduled post_game_updates_job", "bot")
            self.jobs_scheduled = True
            scheduler = AsyncIOScheduler()
            scheduler.add_job(
                self.post_game_updates_job,
                CronTrigger(hour="*", minute="8-59/10", second="0"),
            )
            scheduler.start()
