import asyncio
import io
from typing import Literal, Optional

import discord
from discord import app_commands
from discord.ext import commands
from gtts import gTTSAsync

from utils.checks import check_any, command_available, is_owner
from utils.client import VCRolesClient
from utils.types import LogLevel

tts_langs = Literal[
    "af: Afrikaans",
    "ar: Arabic",
    "bn: Bengali",
    "ca: Catalan",
    "cs: Czech",
    "da: Danish",
    "de: German",
    "en: English",
    "es: Spanish",
    "fr: French",
    "hi: Hindi",
    "it: Italian",
    "ja: Japanese",
    "ko: Korean",
    "my: Myanmar (Burmese)",
    "nl: Dutch",
    "no: Norwegian",
    "pl: Polish",
    "pt: Portuguese",
    "ru: Russian",
    "sv: Swedish",
    "th: Thai",
    "tr: Turkish",
    "zh-CN: Chinese",
    "zh: Chinese (Mandarin)",
]


class TTS(commands.Cog):
    def __init__(self, client: VCRolesClient):
        self.client = client

    tts_commands = app_commands.Group(name="tts", description="Text To Speech commands")

    @tts_commands.command()
    @app_commands.describe(
        message="Enter the message you want to read",
        language="Enter the language you want to use (Default: English `en: English`)",
        leave="The bot leaves the voice channel after reading the message (Default: True)",
    )
    async def play(
        self,
        interaction: discord.Interaction,
        message: str,
        language: tts_langs = "en: English",
        leave: bool = True,
    ):
        """Used to make the bot read a message in a voice channel"""
        index = language.find(":")
        language_code = language[0:index]

        if not interaction.guild or not isinstance(interaction.user, discord.Member):
            return await interaction.response.send_message(
                "You must be in a server to use this commannd."
            )

        if not interaction.user.voice:
            return await interaction.response.send_message(
                "You must be in a voice channel to use this commannd."
            )

        guild_data = await self.client.db.get_guild_data(interaction.guild.id)

        if guild_data.ttsEnabled is False:
            return await interaction.response.send_message(
                "TTS isn't enabled in this server."
            )
        if len(message) > 250 and interaction.user.id not in [
            652797071623192576,
            602235481459261440,
        ]:
            return await interaction.response.send_message(
                "The message is over the 250 character limit"
            )

        if guild_data.ttsRole:
            role = interaction.guild.get_role(int(guild_data.ttsRole))
        else:
            role = None

        if role in interaction.user.roles or guild_data.ttsRole is None:
            if interaction.user.voice.channel:
                tts_message = gTTSAsync(text=message, lang=language_code)
                audio_data = await tts_message.get_audio_data()

                # Create a buffer
                buffer = io.BytesIO(audio_data)

                # Set the buffer to the beginning
                buffer.seek(0)

                vc: Optional[discord.VoiceClient] = None

                for x in self.client.voice_clients:
                    if not isinstance(x, discord.VoiceClient):
                        continue
                    if x.guild.id == interaction.guild.id:
                        vc = x
                        break

                if vc and vc.is_playing():
                    return await interaction.response.send_message(
                        "Please wait for the current TTS message to finish."
                    )

                if not isinstance(vc, discord.VoiceClient):
                    try:
                        vc = await interaction.user.voice.channel.connect()
                    except discord.ClientException:
                        return await interaction.response.send_message(
                            "Cannot connect to a voice channel I'm already in."
                        )
                    except discord.HTTPException:
                        return await interaction.response.send_message(
                            "Failed to connect to the voice channel."
                        )

                embed = discord.Embed(
                    color=discord.Color.green(),
                    title="**Reading Message**",
                    description=f"Reading the message sent by {interaction.user.mention} in the voice channel {interaction.user.voice.channel.mention}",
                )
                await interaction.response.send_message(embed=embed)

                vc.play(
                    discord.FFmpegOpusAudio(
                        source=buffer, before_options="-f mp3", pipe=True
                    )
                )

                # Wait for the audio to finish playing
                while vc.is_playing():
                    await asyncio.sleep(1)

                if leave and guild_data.ttsLeave:
                    await vc.disconnect()

            else:
                await interaction.response.send_message(
                    "You must be in a voice channel to use this command"
                )

        else:
            await interaction.response.send_message(
                "You don't have the required role to use TTS"
            )

        self.client.log(
            LogLevel.DEBUG,
            f"TTS played: g/{interaction.guild.id} m/{interaction.user.id}",
        )

    @tts_commands.command()
    async def stop(self, interaction: discord.Interaction):
        """Stops the current TTS message & Makes the bot leave the voice channel"""
        for x in self.client.voice_clients:
            if not isinstance(x, discord.VoiceClient):
                continue
            if x.guild.id == interaction.guild_id and interaction.guild_id:
                await x.disconnect()
                embed = discord.Embed(
                    colour=discord.Color.green(),
                    description="The current TTS message has been stopped.",
                )
                await interaction.response.send_message(embed=embed)

        embed = discord.Embed(
            colour=discord.Color.green(),
            description="There are no TTS messages being read at the minute",
        )
        await interaction.response.send_message(embed=embed)

        self.client.log(
            LogLevel.DEBUG,
            f"TTS stopped: g/{interaction.guild_id} m/{interaction.user.id}",
        )

    @tts_commands.command()
    @app_commands.describe(
        enabled="Whether or not TTS is enabled in this server",
        role="The role required to use TTS (Default: None)",
        leave="Whether the bot leaves the voice channel after reading the message (Default: True)",
    )
    @check_any(command_available, is_owner)
    @app_commands.checks.has_permissions(administrator=True)
    async def setup(
        self,
        interaction: discord.Interaction,
        enabled: bool,
        role: Optional[discord.Role] = None,
        leave: Optional[bool] = True,
    ):
        """Used to enable/disable TTS & set a required role"""

        if not interaction.guild:
            return await interaction.response.send_message(
                "You must be in a server to use this command."
            )

        await self.client.db.update_guild_data(
            interaction.guild.id,
            tts_enabled=enabled,
            tts_leave=leave,
            tts_role=str(role.id) if role else "None",
        )

        await interaction.response.send_message(
            f"TTS settings updated: Enabled {enabled}, Role {role}, Leave {leave}"
        )

        self.client.log(
            LogLevel.DEBUG,
            f"TTS setup: g/{interaction.guild.id} m/{interaction.user.id}",
        )


async def setup(client: VCRolesClient):
    await client.add_cog(TTS(client))
