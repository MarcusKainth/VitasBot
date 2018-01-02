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

import aiohttp
import asyncio
import discord
import colorlog

from collections import defaultdict

from discord.enums import ChannelType

from .commands import Commands
from .config import ConfigDefaults
from .constants import VERSION as BOTVERSION
from .constants import DISCORD_MSG_CHAR_LIMIT
from .utils import __func__, load_opus_lib

load_opus_lib()

log = logging.getLogger(__name__)

class VitasBot(discord.Client):
    
    def __init__(self, config=None):
        if config is None:
            config = ConfigDefaults()

        self.config = config
        self.commands = Commands(self)
        self.players = {}
        self.now_playing = {}
        self.last_status = None
        self.exit_signal = None

        if self.config.proxy:
            self.connector = aiohttp.ProxyConnector(proxy=self.config.proxy)
        else:
            self.connector = aiohttp.TCPConnector()

        self.aiolocks = defaultdict(asyncio.Lock)
        
        self._setup_logging()

        options = {
            "connector": self.connector
        }

        super().__init__(loop=None, **options)

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

    async def join_voice_channel(self, channel):
        if isinstance(channel, discord.Object):
            channel = self.get_channel(channel.id)

        if getattr(channel, "type", ChannelType.text) != ChannelType.voice:
            raise discord.InvalidArgument(
                "Channel passed must be a voice channel")

        server = channel.server

        if self.is_voice_connected(server):
            raise discord.ClientException(
                "Already conenct to voice channel in server {0}".format(
                    server.name
                ))

        def session_id_found(data):
            user_id = data.get("user_id")
            guild_id = data.get("guild_id")
            return user_id == self.user.id and guild_id == server.id

        log.debug("({0}) Creating futures".format(__func__()))
        # register the futures for waiting
        session_id_future = self.ws.wait_for('VOICE_STATE_UPDATE', session_id_found)
        voice_data_future = self.ws.wait_for('VOICE_SERVER_UPDATE', lambda d: d.get('guild_id') == server.id)

        log.debug("({0}) Setting voice state".format(__func__()))
        await self.ws.voice_state(server.id, channel.id)

        log.debug("({0}) Waiting for session id".format(__func__()))
        session_id_data = await asyncio.wait_for(session_id_future, timeout=15, loop=self.loop)

        log.debug("({0}) Waiting for voice data".format(__func__()))
        data = await asyncio.wait_for(voice_data_future, timeout=15, loop=self.loop)

        kwargs ={
            "user": self.user,
            "channel": channel,
            "data": data,
            "loop": self.loop,
            "session_id": session_id_data.get("session_id"),
            "main_ws": self.ws
        }

        voice = discord.VoiceClient(**kwargs)

        try:
            log.debug("({0}) Connecting...".format(__func__()))
            
            with aiohttp.Timeout(15):
                await voice.connect()
        except asyncio.TimeoutError as e:
            log.debug("({0}) Connection failed, disconnecting...".format(__func__()))

            try:
                await voice.disconenct()
            except:
                pass

            log.debug("({0}) Disconnected successfully".format(__func__()))

            raise e

        log.debug("({0}) Connected successfully".format(__func__()))

        self.connection._add_voice_client(server.id, voice)
        return voice

    async def get_player(self, channel):
        server = channel.server

        if server.id not in self.players:
            raise Exception(
                "The bot is not in a voice channel"
            )
        
        return self.players[server.id]

    async def on_message(self, message):
        await self.wait_until_ready()

        if message.author == self.user:
            log.warning("Ignoring messages from myself: {0}".format(
                message.content))
            return

        if message.author.id not in self.config.owner_id:
            log.warning("Ignoring messages from user ({0}/{1}#{2}): {3}".format(
                message.author.id, message.author.name, message.author.discriminator,
                message.content))
            return

        message_content = message.content.strip()

        if not message_content.startswith(self.config.command_prefix):
            return

        command, *args = message_content.split(' ')
        command = command[len(self.config.command_prefix):].lower().strip()

        handler = getattr(self.commands, "cmd_" + command, None)

        if not handler:
            return

        msg = None

        args.insert(0, message.channel)

        msg = await handler(*args)

        #kwargs = {
        #    "tts": False,
        #    "quiet": False,
        #    "expire_in": 10
        #}

        if msg:
            #await self.safe_send_message(message.channel, msg, **kwargs)
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

        if type(self.config.owner_id) is not list:
            self.config.owner_id = [self.config.owner_id]

        for i, s in enumerate(self.config.owner_id):
            self.config.owner_id[i] = s.strip()
            owner = self._get_member_from_id(self.config.owner_id[i])

            if owner and self.servers:
                log.info("Owner: {0}/{1}#{2}".format(
                    owner.id,
                    owner.name,
                    owner.discriminator
                ))

                log.info("Server list:")
                [log.info(" - {0}".format(s.name)) for s in self.servers]
            elif self.servers:
                log.info("Owner could not be found on any server (id: {0})".format(
                    owner_id
                ))

                log.info("Server list:")
                [log.info(" - {0}".format(s.name)) for s in self.servers]
            else:
                log.info("Owner unknown, bot is not on any servers")

        bot_member = self._get_member_from_id(self.user.id)

        if bot_member.nick != self.config.nickname:
            log.info("Changing nickname to {0}".format(self.config.nickname))
            await self.change_nickname(bot_member, nickname=self.config.nickname)

    def remove_player(self, channel):
        try:
            self.players.pop(channel.server.id)

            if channel.server.id in self.now_playing:
                self.now_playing.pop(channel.server.id)

                coro = self.change_presence(game=None,
                    status=discord.Status.online, afk=False)

                self.loop.run_until_complete(coro)
        except:
            pass
        finally:
            self.loop.close()

    async def update_playing_presence(self, song=None, is_paused=False):
        game = None

        if self.user.bot:
            active_players = sum(1 for p in self.players.values() if p.is_playing())

            if active_players > 1:
                game = discord.Game(name="music on {0} servers".format(
                    active_players))
                song = None
            elif active_players == 1:
                player = discord.utils.get(self.players.values(), is_playing=True)
                # TODO: Get song from player

        if song:
            prefix = u"\u275A\u275A " if is_paused else u"\u25B6 "
            name = "{0}{1}".format(prefix, song)[:128]
            game = discord.Game(name=name)

        async with self.aiolocks[__func__()]:
            if game != self.last_status:
                await self.change_presence(game=game)
                self.last_status = game