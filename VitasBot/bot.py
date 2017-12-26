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
import sys
import logging

import asyncio
import discord
import colorlog

from textwrap import dedent

from .config import ConfigDefaults

from .constants import VERSION as BOTVERSION
from .constants import DISCORD_MSG_CHAR_LIMIT

discord.opus.load_opus("libopus-0.x64.dll")

log = logging.getLogger(__name__)

class VitasBot(discord.Client):
    
    def __init__(self, config=None):
        if config is None:
            config = ConfigDefaults()

        self.config = config
        self.exit_signal = None
        
        self._setup_logging()

        super().__init__()

        self.http.user_agent += " VitasBot/{0}".format(str(BOTVERSION))

    def _setup_logging(self):
        if len(logging.getLogger(__package__).handlers) > 1:
            log.debug("Skip logging setup, already complete")
            return

        shandler = logging.StreamHandler(stream=sys.stdout)
        shandler.setFormatter(colorlog.LevelFormatter(
            fmt = {
                "DEBUG": "{log_color}[{levelname}:{module}] {message}",
                "INFO": "{log_color}{message}",
                "WARNING": "{log_color}{levelname}: {message}",
                "ERROR": "{log_color}[{levelname}:{module}] {message}",
                "CRITICAL": "{log_color}[{levelname}:{module}] {message}"
            },
            log_colors = {
                "DEBUG":    "cyan",
                "INFO":     "white",
                "WARNING":  "yellow",
                "ERROR":    "red",
                "CRITICAL": "bold_red"
            },
            style = '{',
            datefmt = ''
        ))

        log.setLevel(self.config.debug_level)
        shandler.setLevel(self.config.debug_level)
        logging.getLogger(__package__).addHandler(shandler)

        log.debug("Set logging level to {0}".format(self.config.debug_level))

        if self.config.debug_mode:
            dlogger = logging.getLogger("discord")
            dlogger.setLevel(logging.DEBUG)
            os.makedirs("logs", mode=0o644, exist_ok=True)
            dhandler = logging.FileHandler(filename="logs/discord.log", encoding="utf-8", mode='w')
            dhandler.setFormatter(logging.Formatter("{asctime}:{levelname}:{name}: {message}", style='{'))
            dlogger.addHandler(dhandler)

    def _get_member_from_id(self, user_id, *, server=None, voice=False):
        return discord.utils.find(
            lambda m: m.id == user_id and (m.voice_channel if voice else True),
            server.members if server else self.get_all_members()
        )

    def _cleanup(self):
        try:
            self.loop.run_until_complete(self.logout())
        except:
            pass

        pending = asyncio.Task.all_tasks()
        gathered = asyncio.gather(*pending)
        
        try:
            gathered.cancel()
            self.loop.run_until_complete(gathered)
            gathered.exception()
        except:
            pass

    # noinspection PyMethodOverriding
    def run(self):
        try:
            self.loop.run_until_complete(self.start(self.config.token))
        except discord.errors.LoginFailure:
            log.critical("Bot cannot login, "
                "bad credentials.")
        except KeyboardInterrupt:
            self.loop.run_until_complete(self.logout())
        finally:
            try:
                self._cleanup()
            except Exception:
                log.critical("Error on cleanup")

            self.loop.close()

            if self.exit_signal:
                raise self.exit_signal

    def stream(self, voice, song):
        filename, file_extension = os.path.splitext(song)
        now_playing = "Now playing: {}".format(filename)
        log.info(now_playing)
        #await client.send_message((discord.Object(id="324635620301340672")), now_playing)

        player = voice.create_ffmpeg_player(song, before_options="-re", options="-nostats -loglevel 0", after=lambda: self.stream(voice, song))
        player.start()

    async def on_message(self, message):
        await self.wait_until_ready()

        if message.author == self.user:
            log.warning("Ignoring messages from myself: {0}".format(
                message.content))
            return

        if message.author.id != self.config.owner_id:
            log.warning("Ignoring messages from user ({0}/{1}#{2}): {3}".format(
                message.author.id, message.author.name, message.author.discriminator,
                message.content))
            return

        message_content = message.content.strip()

        if not message_content.startswith(self.config.command_prefix):
            return

        command, *args = message_content.split(' ')
        command = command[len(self.config.command_prefix):].lower().strip()

        handler = getattr(self, "cmd_" + command, None)

        print(args)

        if not handler:
            return

        msg = await handler(*args)

        if msg:
            await self.safe_send_message(message.channel, msg)

    async def safe_send_message(self, dest, content, **kwargs):
        tts = kwargs.pop("tts", False)
        quiet = kwargs.pop("quiet", False)
        expire_in = kwargs.pop("expire_in", 0)

        msg = None

        try:
            if content is not None:
                msg = await self.send_message(dest, content, tts=tts)
        except discord.Forbidden:
            log.error("Unable to send message to {0}, no permission".format(
                dest.name))
        except discord.NotFound:
            log.error("Unable to send message to {0}, invalid channel?".format(
                dest.name))
        except discord.HTTPException:
            if len(content) > DISCORD_MSG_CHAR_LIMIT:
                log.error("Message over the size limit {0}/{1}".format(
                    len(content), DISCORD_MSG_CHAR_LIMIT))
            else:
                log.error("Failed to send message, "
                    "got HTTPException to {0} with {1}".format(
                    dest.name, content
                ))
        finally:
            if msg and expire_in:
                asyncio.ensure_future(self._wait_delete_msg(msg, expire_in))

        return msg

    async def safe_delete_message(self, msg):
        try:
            return await self.delete_message(msg)
        except discord.Forbidden:
            log.error("Unable to send message {0}, no permission".format(
                msg.clean_content))
        except discord.NotFound:
            log.error("Unable to send message {0}, invalid channel?".format(
                msg.clean_content))

    async def _wait_delete_msg(self, msg, after):
        await asyncio.sleep(after)
        await self.safe_delete_message(msg)

    async def on_ready(self):
        log.info("Bot:   {0}/{1}#{2}{3}".format(
                self.user.id,
                self.user.name,
                self.user.discriminator,
                " [BOT]" if self.user.bot else " [UserBOT]"
        ))

        owner = self._get_member_from_id(self.config.owner_id)

        if owner and self.servers:
            log.info("Owner: {0}/{1}#{2}".format(
                owner.id,
                owner.name,
                owner.discriminator
            ))

            log.info("\nServer list:")
            [log.info(" - {0}".format(s.name)) for s in self.servers]
        elif self.servers:
            log.info("Owner could not be found on any server (id: {0})".format(
                self.config.owner_id
            ))

            log.info("\nServer list:")
            [log.info(" - {0}".format(s.name)) for s in self.servers]
        else:
            log.info("\nOwner unknown, bot is not on any servers")

        log.info("\nChanging nickname to {0}".format(self.config.nickname))
        await self.change_nickname(self._get_member_from_id(self.user.id), nickname=self.config.nickname)

        channel = self.get_channel(str(self.config.channel_id))
        voice = await self.join_voice_channel(channel)

        log.info("Bot joined channel {0}\n".format(self.config.channel_id))

    async def cmd_help(self, command=None):
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
                    command_prefix=self.config.command_prefix)
            else:
                msg = "No such command"
        else:
            msg = "**Available commands**\n```"
            commands = []

            for func in dir(self):
                if func.startswith("cmd_"):
                    cmd_name = func.replace("cmd_", "").lower()
                    commands.append("{0}{1}".format(self.config.command_prefix, cmd_name))

            msg += "\n".join(commands)
            msg += "```\nYou can also use `{0}help x` for more info about each command.".format(
                self.config.command_prefix
            )

        return msg