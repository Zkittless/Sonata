import discord
from discord import app_commands

DJ_ROLE_NAME = "DJ"

def is_dj_or_admin():
    """Check: user must have DJ role or Administrator permission."""
    async def predicate(interaction: discord.Interaction) -> bool:
        if interaction.user.guild_permissions.administrator:
            return True
        dj_role = discord.utils.get(interaction.guild.roles, name=DJ_ROLE_NAME)
        if dj_role and dj_role in interaction.user.roles:
            return True
        await interaction.response.send_message(
            embed=discord.Embed(
                description="✦ You need the **DJ** role or Admin permissions to use this command.",
                color=0xFF6B8A
            ),
            ephemeral=True
        )
        return False
    return app_commands.check(predicate)

def is_in_voice():
    """Check: user must be in a voice channel."""
    async def predicate(interaction: discord.Interaction) -> bool:
        if not interaction.user.voice:
            await interaction.response.send_message(
                embed=discord.Embed(
                    description="✦ You need to be in a voice channel first! 🎙️",
                    color=0xFF6B8A
                ),
                ephemeral=True
            )
            return False
        return True
    return app_commands.check(predicate)
