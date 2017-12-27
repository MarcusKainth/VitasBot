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
import configparser

class Config:
    def __init__(self, config_file):
        self.config_file = config_file

        config = configparser.ConfigParser(interpolation=None)
        config.read(config_file, encoding="utf-8")

        config_sections = {"User", "Permissions", "Credentials", "Channel",
                           "Music", "Pictures", "Console"}.difference(
                           config.sections())

        if config_sections:
            raise Exception(
                "One or more sections in the configuration file are missing.",
                "Fix the configuration file. Each [Section] should have its "
                "own line with nothing else on it. The following are missing: "
                "{0}".format(", ".join(["[%s]" % s for s in config_sections])
                )
            )

        self.nickname = config.get("User", "Nickname")
        self.token = config.get("Credentials", "Token")
        self.owner_id = config.get("Permissions", "OwnerID")
        self.channel_id = config.get("Channel", "ChannelID")
        self.command_prefix = config.get("Channel", "CommandPrefix")
        self.volume = config.get("Music", "Volume")
        self.music_dir = config.get("Music", "Directory")
        self.pictures_dir = config.get("Pictures", "Directory")
        self.debug_level = config.get("Console", "DebugLevel")
        self.debug_mode = config.get("Console", "DebugMode")

class ConfigDefaults:
    def __init__(self):
        self.nickname = None
        self.token = "TOKEN_HERE"
        self.owner_id = 000000000000000000
        self.channel_id = 000000000000000000