import discord
from discord import app_commands
from discord.ext import commands
import aiohttp
from utils.theme import PINK_MAIN, PINK_ERROR, PINK_LIGHT, SPARKLE, NOTE

class Lyrics(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="lyrics", description="Get lyrics for the current song or a search query 🎤")
    @app_commands.describe(query="Song name to search (leave blank for current song)")
    async def lyrics(self, interaction: discord.Interaction, query: str = None):
        await interaction.response.defer()

        # If no query, try to get current song
        if not query:
            from cogs.music import Music
            music_cog: Music = self.bot.get_cog("Music")
            if music_cog:
                state = music_cog.get_state(interaction.guild_id)
                if state.current:
                    query = state.current.title
            if not query:
                return await interaction.followup.send(
                    embed=discord.Embed(
                        description=f"{SPARKLE} No song is playing. Provide a song name!",
                        color=PINK_ERROR
                    )
                )

        # Fetch from lyrics.ovh (free, no key needed)
        search = query.strip()
        parts  = search.split(" ", 1)
        artist = parts[0] if len(parts) > 0 else search
        title  = parts[1] if len(parts) > 1 else search

        async with aiohttp.ClientSession() as session:
            try:
                url  = f"https://api.lyrics.ovh/v1/{artist}/{title}"
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=8)) as resp:
                    if resp.status == 200:
                        data   = await resp.json()
                        lyrics = data.get("lyrics", "")
                    else:
                        # Try swapped (title as artist)
                        url2 = f"https://api.lyrics.ovh/v1/{title}/{artist}"
                        async with session.get(url2, timeout=aiohttp.ClientTimeout(total=8)) as resp2:
                            if resp2.status == 200:
                                data   = await resp2.json()
                                lyrics = data.get("lyrics", "")
                            else:
                                lyrics = ""
            except Exception:
                lyrics = ""

        if not lyrics:
            return await interaction.followup.send(
                embed=discord.Embed(
                    description=f"{SPARKLE} Couldn't find lyrics for **{search}**. Try a more specific search!",
                    color=PINK_ERROR
                )
            )

        # Trim if too long for Discord
        MAX = 3900
        if len(lyrics) > MAX:
            lyrics = lyrics[:MAX] + "\n\n*...lyrics truncated*"

        embed = discord.Embed(
            title=f"{NOTE}  Lyrics — {search}",
            description=lyrics,
            color=PINK_MAIN
        )
        embed.set_footer(text="Sonata 🌸  •  Lyrics via lyrics.ovh")
        await interaction.followup.send(embed=embed)

async def setup(bot: commands.Bot):
    await bot.add_cog(Lyrics(bot))
