import discord
from discord import app_commands
from discord.ext import commands
import yt_dlp
import asyncio
import spotipy
from spotipy.oauth2 import SpotifyClientCredentials
import os
import re
from collections import deque
from utils.theme import (
    PINK_MAIN, PINK_HOT, PINK_LIGHT, PINK_ERROR, PINK_SUCCESS,
    bar, fmt_duration, NOTE, SPARKLE
)
from utils.checks import is_dj_or_admin, is_in_voice

# ── yt-dlp options ────────────────────────────────────────────────────────────
YDL_OPTS = {
    "format": "bestaudio/best",
    "quiet": True,
    "no_warnings": True,
    "default_search": "ytsearch",
    "noplaylist": True,
    "extract_flat": False,
}

FFMPEG_OPTS = {
    "before_options": "-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5",
    "options": "-vn",
}

# ── Song dataclass ─────────────────────────────────────────────────────────────
class Song:
    def __init__(self, data: dict, requester: discord.Member):
        self.title     = data.get("title", "Unknown")
        self.url       = data.get("webpage_url") or data.get("url", "")
        self.stream    = data.get("url", "")
        self.duration  = data.get("duration", 0)
        self.thumbnail = data.get("thumbnail", "")
        self.uploader  = data.get("uploader", "Unknown")
        self.requester = requester

# ── Guild music state ──────────────────────────────────────────────────────────
class MusicState:
    def __init__(self):
        self.queue: deque[Song] = deque()
        self.current: Song | None = None
        self.volume: float = 0.5
        self.loop: bool = False
        self.now_playing_msg: discord.Message | None = None

# ── Now Playing View (buttons) ─────────────────────────────────────────────────
class NowPlayingView(discord.ui.View):
    def __init__(self, cog: "Music"):
        super().__init__(timeout=None)
        self.cog = cog

    async def _get_state(self, interaction: discord.Interaction):
        return self.cog.states.get(interaction.guild_id)

    @discord.ui.button(emoji="⏸", style=discord.ButtonStyle.primary, custom_id="pause_resume")
    async def pause_resume(self, interaction: discord.Interaction, button: discord.ui.Button):
        vc = interaction.guild.voice_client
        if not vc:
            return await interaction.response.send_message("Not connected.", ephemeral=True)
        if vc.is_paused():
            vc.resume()
            button.emoji = "⏸"
            await interaction.response.edit_message(view=self)
        elif vc.is_playing():
            vc.pause()
            button.emoji = "▶️"
            await interaction.response.edit_message(view=self)
        else:
            await interaction.response.defer()

    @discord.ui.button(emoji="⏭", style=discord.ButtonStyle.primary, custom_id="skip")
    async def skip(self, interaction: discord.Interaction, button: discord.ui.Button):
        vc = interaction.guild.voice_client
        if vc and (vc.is_playing() or vc.is_paused()):
            vc.stop()
            await interaction.response.send_message(
                embed=discord.Embed(description=f"{SPARKLE} Skipped!", color=PINK_MAIN),
                ephemeral=True
            )
        else:
            await interaction.response.send_message("Nothing to skip.", ephemeral=True)

    @discord.ui.button(emoji="🔁", style=discord.ButtonStyle.primary, custom_id="loop")
    async def loop_toggle(self, interaction: discord.Interaction, button: discord.ui.Button):
        state = await self._get_state(interaction)
        if not state:
            return await interaction.response.defer()
        state.loop = not state.loop
        button.style = discord.ButtonStyle.success if state.loop else discord.ButtonStyle.primary
        await interaction.response.edit_message(view=self)

    @discord.ui.button(emoji="🔀", style=discord.ButtonStyle.primary, custom_id="shuffle")
    async def shuffle(self, interaction: discord.Interaction, button: discord.ui.Button):
        state = await self._get_state(interaction)
        if state and len(state.queue) > 1:
            import random
            queue_list = list(state.queue)
            random.shuffle(queue_list)
            state.queue = deque(queue_list)
            await interaction.response.send_message(
                embed=discord.Embed(description=f"{SPARKLE} Queue shuffled! 🔀", color=PINK_MAIN),
                ephemeral=True
            )
        else:
            await interaction.response.send_message("Not enough songs to shuffle.", ephemeral=True)

    @discord.ui.button(emoji="⏹", style=discord.ButtonStyle.danger, custom_id="stop")
    async def stop(self, interaction: discord.Interaction, button: discord.ui.Button):
        state = await self._get_state(interaction)
        vc = interaction.guild.voice_client
        if state:
            state.queue.clear()
            state.current = None
        if vc:
            await vc.disconnect()
        await interaction.response.send_message(
            embed=discord.Embed(description=f"{SPARKLE} Stopped and disconnected. Bye! 🌸", color=PINK_ERROR),
            ephemeral=True
        )

# ── Music Cog ─────────────────────────────────────────────────────────────────
class Music(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot    = bot
        self.states: dict[int, MusicState] = {}

        # Spotify client
        sp_id     = os.getenv("SPOTIFY_CLIENT_ID")
        sp_secret = os.getenv("SPOTIFY_CLIENT_SECRET")
        if sp_id and sp_secret:
            self.sp = spotipy.Spotify(
                auth_manager=SpotifyClientCredentials(
                    client_id=sp_id,
                    client_secret=sp_secret
                )
            )
        else:
            self.sp = None

    def get_state(self, guild_id: int) -> MusicState:
        if guild_id not in self.states:
            self.states[guild_id] = MusicState()
        return self.states[guild_id]

    # ── Spotify helpers ────────────────────────────────────────────────────────
    def is_spotify_url(self, query: str) -> bool:
        return "open.spotify.com" in query

    async def resolve_spotify(self, url: str) -> list[str]:
        """Returns a list of search queries from a Spotify track/playlist/album."""
        if not self.sp:
            return []
        loop = asyncio.get_event_loop()

        def _fetch():
            if "track" in url:
                data = self.sp.track(url)
                name   = data["name"]
                artist = data["artists"][0]["name"]
                return [f"{name} {artist}"]
            elif "playlist" in url:
                results = self.sp.playlist_tracks(url)
                queries = []
                for item in results["items"][:25]:  # cap at 25
                    t = item.get("track")
                    if t:
                        queries.append(f"{t['name']} {t['artists'][0]['name']}")
                return queries
            elif "album" in url:
                data = self.sp.album_tracks(url)
                queries = []
                for t in data["items"][:25]:
                    queries.append(f"{t['name']} {t['artists'][0]['name']}")
                return queries
            return []

        return await loop.run_in_executor(None, _fetch)

    # ── yt-dlp helpers ─────────────────────────────────────────────────────────
    async def fetch_song(self, query: str, requester: discord.Member) -> Song | None:
        loop = asyncio.get_event_loop()
        if not re.match(r"https?://", query):
            query = f"ytsearch:{query}"

        def _extract():
            with yt_dlp.YoutubeDL(YDL_OPTS) as ydl:
                info = ydl.extract_info(query, download=False)
                if "entries" in info:
                    info = info["entries"][0]
                return info

        try:
            data = await loop.run_in_executor(None, _extract)
            return Song(data, requester)
        except Exception as e:
            print(f"yt-dlp error: {e}")
            return None

    # ── Playback ───────────────────────────────────────────────────────────────
    async def play_next(self, guild: discord.Guild, channel: discord.TextChannel):
        state = self.get_state(guild.id)
        vc    = guild.voice_client

        if not vc:
            return

        if state.loop and state.current:
            song = await self.fetch_song(state.current.url, state.current.requester)
        elif state.queue:
            song = state.queue.popleft()
        else:
            state.current = None
            embed = discord.Embed(
                description=f"{SPARKLE} Queue finished. See you next time! 🌸",
                color=PINK_LIGHT
            )
            await channel.send(embed=embed)
            return

        state.current = song

        source = discord.FFmpegPCMAudio(song.stream, **FFMPEG_OPTS)
        source = discord.PCMVolumeTransformer(source, volume=state.volume)

        def after(error):
            if error:
                print(f"Playback error: {error}")
            asyncio.run_coroutine_threadsafe(
                self.play_next(guild, channel), self.bot.loop
            )

        vc.play(source, after=after)
        await self.send_now_playing(channel, state, guild)

    async def send_now_playing(self, channel: discord.TextChannel, state: MusicState, guild: discord.Guild):
        song = state.current
        if not song:
            return

        progress = bar(0, song.duration)
        duration_str = fmt_duration(song.duration) if song.duration else "Live"

        embed = discord.Embed(
            title=f"{NOTE}  Now Playing",
            description=f"### [{song.title}]({song.url})\n{progress}  `0:00 / {duration_str}`",
            color=PINK_MAIN
        )
        embed.set_thumbnail(url=song.thumbnail)
        embed.add_field(name="Uploaded by", value=song.uploader, inline=True)
        embed.add_field(name="Requested by", value=song.requester.mention, inline=True)
        embed.add_field(name="Queue", value=f"{len(state.queue)} song(s) up next", inline=True)
        embed.set_footer(text="Sonata 🌸  •  Use the buttons below to control playback")

        view = NowPlayingView(self)

        # Delete old now playing message
        if state.now_playing_msg:
            try:
                await state.now_playing_msg.delete()
            except Exception:
                pass

        msg = await channel.send(embed=embed, view=view)
        state.now_playing_msg = msg

    # ── /play ──────────────────────────────────────────────────────────────────
    @app_commands.command(name="play", description="Play a song or Spotify link 🎵")
    @app_commands.describe(query="Song name, YouTube URL, or Spotify link")
    async def play(self, interaction: discord.Interaction, query: str):
        if not interaction.user.voice:
            return await interaction.response.send_message(
                embed=discord.Embed(description="✦ Join a voice channel first! 🎙️", color=PINK_ERROR),
                ephemeral=True
            )

        await interaction.response.defer()
        state = self.get_state(interaction.guild_id)
        vc    = interaction.guild.voice_client

        # Connect to voice
        if not vc:
            vc = await interaction.user.voice.channel.connect()
        elif vc.channel != interaction.user.voice.channel:
            await vc.move_to(interaction.user.voice.channel)

        # Resolve Spotify
        if self.is_spotify_url(query):
            if not self.sp:
                return await interaction.followup.send(
                    embed=discord.Embed(
                        description="✦ Spotify credentials not configured. Add them to `.env`!",
                        color=PINK_ERROR
                    )
                )
            queries = await self.resolve_spotify(query)
            if not queries:
                return await interaction.followup.send(
                    embed=discord.Embed(description="✦ Couldn't resolve that Spotify link.", color=PINK_ERROR)
                )

            loading = discord.Embed(
                description=f"{SPARKLE} Loading **{len(queries)}** track(s) from Spotify... 🌸",
                color=PINK_LIGHT
            )
            await interaction.followup.send(embed=loading)

            first = True
            for q in queries:
                song = await self.fetch_song(q, interaction.user)
                if song:
                    if first and not vc.is_playing():
                        state.current = song
                        source = discord.FFmpegPCMAudio(song.stream, **FFMPEG_OPTS)
                        source = discord.PCMVolumeTransformer(source, volume=state.volume)

                        def after(error):
                            asyncio.run_coroutine_threadsafe(
                                self.play_next(interaction.guild, interaction.channel), self.bot.loop
                            )
                        vc.play(source, after=after)
                        await self.send_now_playing(interaction.channel, state, interaction.guild)
                        first = False
                    else:
                        state.queue.append(song)
            return

        # Single YouTube/search
        song = await self.fetch_song(query, interaction.user)
        if not song:
            return await interaction.followup.send(
                embed=discord.Embed(description="✦ Couldn't find that song. Try a different search!", color=PINK_ERROR)
            )

        if vc.is_playing() or vc.is_paused():
            state.queue.append(song)
            embed = discord.Embed(
                title=f"{SPARKLE} Added to Queue",
                description=f"[{song.title}]({song.url})",
                color=PINK_HOT
            )
            embed.set_thumbnail(url=song.thumbnail)
            embed.add_field(name="Position", value=f"#{len(state.queue)}", inline=True)
            embed.add_field(name="Duration", value=fmt_duration(song.duration), inline=True)
            embed.set_footer(text="Sonata 🌸")
            await interaction.followup.send(embed=embed)
        else:
            state.current = song
            source = discord.FFmpegPCMAudio(song.stream, **FFMPEG_OPTS)
            source = discord.PCMVolumeTransformer(source, volume=state.volume)

            def after(error):
                asyncio.run_coroutine_threadsafe(
                    self.play_next(interaction.guild, interaction.channel), self.bot.loop
                )
            vc.play(source, after=after)
            await self.send_now_playing(interaction.channel, state, interaction.guild)
            await interaction.followup.send(
                embed=discord.Embed(description=f"{SPARKLE} Starting playback! 🌸", color=PINK_SUCCESS),
                ephemeral=True
            )

    # ── /queue ─────────────────────────────────────────────────────────────────
    @app_commands.command(name="queue", description="View the current queue 🎶")
    async def queue_cmd(self, interaction: discord.Interaction):
        state = self.get_state(interaction.guild_id)
        if not state.current and not state.queue:
            return await interaction.response.send_message(
                embed=discord.Embed(description=f"{SPARKLE} The queue is empty. Add some songs! 🌸", color=PINK_LIGHT),
                ephemeral=True
            )

        embed = discord.Embed(title=f"{NOTE}  Sonata Queue", color=PINK_MAIN)

        if state.current:
            embed.add_field(
                name="▶  Now Playing",
                value=f"[{state.current.title}]({state.current.url}) — `{fmt_duration(state.current.duration)}`\nRequested by {state.current.requester.mention}",
                inline=False
            )

        if state.queue:
            lines = []
            for i, song in enumerate(list(state.queue)[:10], 1):
                lines.append(f"`{i}.` [{song.title}]({song.url}) — `{fmt_duration(song.duration)}`")
            if len(state.queue) > 10:
                lines.append(f"*...and {len(state.queue) - 10} more*")
            embed.add_field(name="Up Next", value="\n".join(lines), inline=False)

        embed.set_footer(text=f"Sonata 🌸  •  {len(state.queue)} song(s) in queue  •  Loop: {'On' if state.loop else 'Off'}")
        await interaction.response.send_message(embed=embed)

    # ── /volume ────────────────────────────────────────────────────────────────
    @app_commands.command(name="volume", description="Set the playback volume (0–100)")
    @app_commands.describe(level="Volume level from 0 to 100")
    async def volume(self, interaction: discord.Interaction, level: int):
        if not 0 <= level <= 100:
            return await interaction.response.send_message(
                embed=discord.Embed(description="✦ Volume must be between 0 and 100.", color=PINK_ERROR),
                ephemeral=True
            )
        state = self.get_state(interaction.guild_id)
        state.volume = level / 100
        vc = interaction.guild.voice_client
        if vc and vc.source:
            vc.source.volume = state.volume

        embed = discord.Embed(
            description=f"{SPARKLE} Volume set to **{level}%** {'🔇' if level == 0 else '🔊'}",
            color=PINK_MAIN
        )
        await interaction.response.send_message(embed=embed)

    # ── /skip ──────────────────────────────────────────────────────────────────
    @app_commands.command(name="skip", description="Skip the current song ⏭")
    async def skip(self, interaction: discord.Interaction):
        vc = interaction.guild.voice_client
        if not vc or not (vc.is_playing() or vc.is_paused()):
            return await interaction.response.send_message(
                embed=discord.Embed(description="✦ Nothing is playing right now.", color=PINK_ERROR),
                ephemeral=True
            )
        vc.stop()
        await interaction.response.send_message(
            embed=discord.Embed(description=f"{SPARKLE} Skipped! ⏭", color=PINK_MAIN)
        )

    # ── /pause ─────────────────────────────────────────────────────────────────
    @app_commands.command(name="pause", description="Pause playback ⏸")
    @is_dj_or_admin()
    async def pause(self, interaction: discord.Interaction):
        vc = interaction.guild.voice_client
        if vc and vc.is_playing():
            vc.pause()
            await interaction.response.send_message(
                embed=discord.Embed(description=f"{SPARKLE} Paused. ⏸", color=PINK_MAIN)
            )
        else:
            await interaction.response.send_message(
                embed=discord.Embed(description="✦ Nothing is playing.", color=PINK_ERROR), ephemeral=True
            )

    # ── /resume ────────────────────────────────────────────────────────────────
    @app_commands.command(name="resume", description="Resume playback ▶️")
    @is_dj_or_admin()
    async def resume(self, interaction: discord.Interaction):
        vc = interaction.guild.voice_client
        if vc and vc.is_paused():
            vc.resume()
            await interaction.response.send_message(
                embed=discord.Embed(description=f"{SPARKLE} Resumed! ▶️", color=PINK_MAIN)
            )
        else:
            await interaction.response.send_message(
                embed=discord.Embed(description="✦ Nothing is paused.", color=PINK_ERROR), ephemeral=True
            )

    # ── /stop ──────────────────────────────────────────────────────────────────
    @app_commands.command(name="stop", description="Stop playback and disconnect ⏹")
    @is_dj_or_admin()
    async def stop(self, interaction: discord.Interaction):
        state = self.get_state(interaction.guild_id)
        state.queue.clear()
        state.current = None
        vc = interaction.guild.voice_client
        if vc:
            await vc.disconnect()
        await interaction.response.send_message(
            embed=discord.Embed(description=f"{SPARKLE} Stopped and disconnected. See you! 🌸", color=PINK_ERROR)
        )

    # ── /remove ────────────────────────────────────────────────────────────────
    @app_commands.command(name="remove", description="Remove a song from the queue by position")
    @app_commands.describe(position="Position in the queue (1 = next up)")
    @is_dj_or_admin()
    async def remove(self, interaction: discord.Interaction, position: int):
        state = self.get_state(interaction.guild_id)
        if position < 1 or position > len(state.queue):
            return await interaction.response.send_message(
                embed=discord.Embed(description="✦ Invalid queue position.", color=PINK_ERROR), ephemeral=True
            )
        queue_list = list(state.queue)
        removed    = queue_list.pop(position - 1)
        state.queue = deque(queue_list)
        await interaction.response.send_message(
            embed=discord.Embed(
                description=f"{SPARKLE} Removed **{removed.title}** from the queue.",
                color=PINK_MAIN
            )
        )

async def setup(bot: commands.Bot):
    await bot.add_cog(Music(bot))
