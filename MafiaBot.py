import random
import traceback
import asyncio
import discord
import json
from discord.ext import commands


def open_json(fn: str):
    """Open a json file and handle the errors."""
    try:
        with open(fn) as f:
            return json.load(f)
    except FileNotFoundError:
        with open(fn, 'w') as f:
            json.dump({}, f)
            return {}


tokens = open_json('tokens.json')


class Config:
    def __init__(self, config_path):
        self.path = config_path
        self._db = open_json(config_path)
        self.__dict__.update(self._db)

    def __getattr__(self, name):
        return self.__dict__.get(name, None)

    def _dump(self):
        for k in self._db:
            self._db[k] = self.__dict__[k]
        with open(self.path, 'w') as f:
            json.dump(self._db, f, ensure_ascii=True)

    async def save(self):
        await asyncio.get_event_loop().run_in_executor(None, self._dump)


class MafiaBot(commands.Bot):
    """Facilitates games of mafia in a discord server"""
    def __init__(self, *args, **kwargs):
        if 'description' not in kwargs:
            kwargs['description'] = """
            Use these commands to run a game of mafia.
            """
        super(MafiaBot, self).__init__(*args, **kwargs)

        self.config = Config('config.json')
        self.content = Config('content.json')

        self.__owner = None
        self.mafia_server = self.get_server(self.content.server)

        self.loop.create_task(self.load_extensions())

    @property
    def owner(self):
        if self.__owner is None:
            return self.user  # fallback to bot user since it is a valid user, though not the owner.
        return self.__owner

    async def update_info(self):
        await self.wait_until_ready()
        self.__owner = (await self.application_info()).owner

    async def load_extensions(self):
        await self.wait_until_ready()
        for ext in self.config.base_extensions:
            try:
                self.load_extension(ext)
            except Exception:
                await self.send_message(self.owner, traceback.format_exc())


bot = MafiaBot(command_prefix='%')


@bot.event
async def on_ready():
    await bot.update_info()
    print('Bot: {0.name}:{0.id}'.format(bot.user))
    print('Owner: {0.name}:{0.id}'.format(bot.owner))
    print('------------------')


if __name__ == '__main__':
    bot.run(tokens['discord_token'])
