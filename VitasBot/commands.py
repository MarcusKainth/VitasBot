# -*- coding: utf-8 -*-

"""
MIT License

Copyright (c) 2017 Marcus Kainth

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
"""

import os
import time
import random
import logging

from discord import Game
from discord import Status

from textwrap import dedent

log = logging.getLogger(__name__)

class Commands:
    def __init__(self, bot):
        self.bot = bot

    async def cmd_help(self, channel, command=None):
        """
        Usage:
            {command_prefix}help [command]

        Prints a help message.
        If a command is specified, a personalised help message is printed
        for that command. Otherwise, all available commands are listed.
        """
        
        msg = None

        if command:
            cmd = getattr(self, "cmd_" + command, None)

            if cmd:
                msg = "```{0}```".format(dedent(cmd.__doc__)).format(
                    command_prefix=self.bot.config.command_prefix)
            else:
                msg = "No such command"
        else:
            msg = "**Available commands**\n```"
            commands = []

            for func in dir(self):
                if func.startswith("cmd_"):
                    cmd_name = func.replace("cmd_", "").lower()
                    commands.append("{0}{1}".format(self.bot.config.command_prefix, cmd_name))

            msg += "\n".join(commands)
            msg += "```\nYou can also use `{0}help x` for more info about each command.".format(
                self.bot.config.command_prefix
            )

        return msg

    async def cmd_join(self, channel, channel_id=None):
        """
        Usage:
            {command_prefix}join [*channel_id]

        * = Optional argument

        Join voice channel on servers the bot is affiliated with.
        """

        voice = self.bot.voice_client_in(channel.server)

        if channel_id is None:
            channel_id = 365610229418950658

        if voice is not None:
            if channel.server.id in self.bot.players:
                player = self.bot.players.pop(channel.server.id)
                player.stop()

            if channel.server.id in self.bot.now_playing:
                self.bot.now_playing.pop(channel.server.id)

                await self.bot.change_presence(game=None,
                    status=Status.online, afk=False)
                    
            await voice.disconnect()

        channel = self.bot.get_channel(str(channel_id))
        voice = await self.bot.join_voice_channel(channel)

    async def cmd_play(self, channel, volume=1.0, song=None):
        """
        Usage:
            {command_prefix}play [*volume] [*song]

        * = Optional argument

        Play song stored on the bot.
        Note: If song is not specified, the bot will pick a song to play 
        from random in the songs directory specified in the configuration
        """
        
        # Pick a random song from the folder
        if song is None:
            songs = [i for i in os.listdir(self.bot.config.music_dir)]
            song = random.choice(songs)

        voice = self.bot.voice_client_in(channel.server)

        if voice is not None:
            if channel.server.id not in self.bot.players:
                path = self.bot.config.music_dir + os.path.sep + song
                filename, file_extension = os.path.splitext(path)
                now_playing = "Now playing: {}".format(filename)
                log.info(now_playing)
                await self.bot.update_playing_presence(song)

                self.bot.players[channel.server.id] = voice.create_ffmpeg_player(path,
                    before_options="-re", options="-nostats -loglevel 0",
                    after=lambda: self.bot.remove_player(channel))
                self.bot.players[channel.server.id].volume = float(volume)
                self.bot.now_playing[channel.server.id] = song
                self.bot.players[channel.server.id].start()
            else:
                raise Exception("Bot is already playing in voice channel")
        else:
            raise Exception("The bot is not part of a voice channel")

    async def cmd_pause(self, channel):
        """
        Usage:
            {command_prefix}pause

        Pauses playback of current song.
        """

        if channel.server.id in self.bot.players:
            player = self.bot.players[channel.server.id]
            if player.is_playing():
                player.pause()
                await self.bot.update_playing_presence(
                    song=self.bot.now_playing[channel.server.id],
                    is_paused=True)
        else:
            raise Exception("Bot is not playing in this server")

    async def cmd_resume(self, channel):
        """
        Usage:
            {command_prefix}resume

        Resumes playback of current song.
        """

        if channel.server.id in self.bot.players:
            player = self.bot.players[channel.server.id]
            if not player.is_playing():
                player.resume()
                await self.bot.update_playing_presence(
                    song=self.bot.now_playing[channel.server.id],
                    is_paused=False)
        else:
            raise Exception("Bot is not playing in this server")

    async def cmd_stop(self, channel):
        """
        Usage:
            {command_prefix}stop

        Stops playback of current song.
        """

        if channel.server.id in self.bot.players:
            player = self.bot.players.pop(channel.server.id)
            player.stop()

            if channel.server.id in self.bot.now_playing:
                self.bot.now_playing.pop(channel.server.id)

                await self.bot.update_playing_presence()
        else:
            raise Exception("Bot is not playing in this server")

    async def cmd_leave(self, channel):
        """
        Usage:
            {command_prefix}leave

        Leaves current voice channel in the server.
        """

        voice = self.bot.voice_client_in(channel.server)

        if voice is not None:
            if channel.server.id in self.bot.players:
                player = self.bot.players.pop(channel.server.id)
                player.stop()

            if channel.server.id in self.bot.now_playing:
                self.bot.now_playing.pop(channel.server.id)

                await self.bot.update_playing_presence()

            await voice.disconnect()
        else:
            raise Exception("Bot is not in any voice channels on this server")

    async def cmd_picture(self, channel):
        """
        Usage:
           {command_prefix}picture

        Posts a fabulous picture of the one and only Vitas
        """

        exts = [".jpg", ".jpeg", ".gif", ".gifv", ".png", ".webm"]
        images = [i for i in os.listdir(self.bot.config.pictures_dir)]

        image = random.choice(images)

        await self.bot.send_file(channel, self.bot.config.pictures_dir + os.path.sep + image)
        return

    async def cmd_ping(self, channel):
        """
        Usage:
            {command_prefix}ping

        Check pseudo-ping to the discord server to ensure connectivity.
        """

        t1 = time.perf_counter()
        await self.bot.send_typing(channel)
        t2 = time.perf_counter()

        msg = "pseudo-ping: {0:.3f}ms".format((t2 - t1) * 1000)

        return msg

    async def cmd_now_playing(self, channel):
        """
        Usage:
            {command_prefix}now_playing

        Sends a message with the current song playing on this server_id.
        """

        if not channel.server.id in self.bot.now_playing:
            raise Exception(
                "The bot is not playing any songs"
            )

        return self.bot.now_playing[channel.server.id]