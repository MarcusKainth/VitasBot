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

import aiohttp
import asyncio
import discord
import os
import sys

discord.opus.load_opus("libopus-0.x64.dll")

class VitasBot(discord.Client):
    
    def __init__(self, token, owner_id, channel_id):
        self.token = token
        self.owner_id = owner_id
        self.channel_id = channel_id

        super().__init__()

    def _get_owner(self, *, server=None, voice=False):
        return discord.utils.find(
            lambda m: m.id == self.owner_id and (m.voice_channel if voice else True),
            server.members if server else self.get_all_members()
        )

    def _get_self(self, *, server=None):
        return discord.utils.find(
            lambda m: m.id == self.user.id,
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
            self.loop.run_until_complete(self.start(self.token))
        except discord.errors.LoginFailure:
            sys.stderr.write("""Bot cannot login,
                bad credentials.""")
        except KeyboardInterrupt:
            self.loop.run_until_complete(self.logout())
        finally:
            try:
                self._cleanup()
            except Exception:
                sys.stderr.write("Error on cleanup")

            self.loop.close()

            if self.exit_signal:
                raise self.exit_signal

    def stream(self, voice, song):
        filename, file_extension = os.path.splitext(song)
        now_playing = "Now playing: {}".format(filename)
        print(now_playing)
        #await client.send_message((discord.Object(id="324635620301340672")), now_playing)

        player = voice.create_ffmpeg_player(song, before_options="-re", options="-nostats -loglevel 0", after=lambda: self.stream(voice, song))
        player.start()

    async def on_ready(self):
        print("Bot:   {0}/{1}#{2}{3}".format(
                self.user.id,
                self.user.name,
                self.user.discriminator,
                " [BOT]" if self.user.bot else " [UserBOT]"
        ))

        owner = self._get_owner(voice=True) or self._get_owner()

        if owner and self.servers:
            print("Owner: {0}/{1}#{2}".format(
                owner.id,
                owner.name,
                owner.discriminator
            ))

            print("\nServer list:")
            [print(" - {0}".format(s.name)) for s in self.servers]
        elif self.servers:
            print("Owner could not be found on any server (id: {0})".format(
                self.owner_id
            ))

            print("\nServer list:")
            [print(" - {0}".format(s.name)) for s in self.servers]
        else:
            print("\nOwner unknown, bot is not on any servers")

        nickname = "Vitaliy Vladasovich Grachov"
        print("\nChanging nickname to {0}".format(nickname))
        await self.change_nickname(self._get_self(), nickname=nickname)

        song = "Vitas - The 7th Element.mp3"
        filename, file_extension = os.path.splitext(song)

        await self.change_presence(game=discord.Game(name=filename), status=discord.Status.online, afk=False)

        channel = self.get_channel(str(self.channel_id))
        voice = await self.join_voice_channel(channel)

        print("Bot joined channel {0}".format(self.channel_id))

        self.stream(voice, song)