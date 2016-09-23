import random
import json
from enum import Enum
import discord
from discord.ext import commands


with open('mafia.json') as f:
    mafia_content = json.load(f)


Character = Enum('Character', mafia_content['characters'])


class MafiaMember:
    def __init__(self, bot: commands.Bot, member: discord.Member, game: str):
        self.bot = bot
        self.member = member
        self.game = game
        self.character = None  # this will be set when the game starts
        self.vote = ""

    async def message(self, m: str):
        """Send a message to a member."""
        await self.bot.send_message(self.member, m)


class MafiaGame:
    def __init__(self, bot: commands.Bot, chan: discord.Channel, role: discord.Role, lead: discord.Member, name: str):
        self.bot = bot
        self.name = name
        self.channel = chan
        self.role = role
        self.leader = lead
        self.members = []
        self.ruleset = mafia_content['rulesets']['default']
        self.state = ''

    @property
    def size(self):
        return len(self.members)

    @property
    def unassigned_members(self):
        return [m for m in self.members if m.character is None]

    def votes(self, v: str):
        return len([m for m in self.members if m.vote == v])

    async def distribute_characters(self):
        # set mafia members
        for _ in range(0, self.size // 3):
            m = random.choice(self.unassigned_members)
            m.character = Character.mafia
        # set one player for each special rule in the ruelset
        for character in self.ruleset:
            m = random.choice(self.unassigned_members)
            m.character = Character[character]
        # set the rest of the players as innocent
        for m in self.unassigned_members:
            m.character = Character.innocent
        for member in self.members:
            await member.message("All character actions should be done here so you don't reveal who you are.")
            await member.message(mafia_content[member.character.name])

    async def night(self):
        await self.bot.send_message(self.channel, "It is now night." +
                                    "\nThe game will progress to morning once all characters perform their action.")


def is_character(character: Character):
    def char_check(ctx):
        mafia = ctx.bot.get_cog("Mafia")
        if not ctx.message.channel.is_private:
            # if someone calls help, it would reveal what actions they have access to and reveal their character
            # so, we only allow this check to pass in private messages
            return False
        if ctx.message.author.id not in mafia.members:
            return False
        if mafia.members[ctx.message.author.id].character == character:
            return True
        return False
    return commands.check(char_check)


def in_game():
    """Check if the player is currently in a game, and in their game channel."""
    def game_check(ctx):
        mafia = ctx.bot.get_cog("Mafia")
        if ctx.message.author.id not in mafia.members:
            return False
        member = mafia.members[ctx.message.author.id]
        if ctx.message.channel == member.game.channel:
            return True
        return False
    return commands.check(game_check)


class Mafia:
    """"""
    player_minimum = 4

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.games = {}
        self.members = {}

    @commands.command(pass_context=True, no_pm=True)
    async def creategame(self, ctx, name: str):
        """Start a game of mafia. The name you give it will be used by others to join."""
        game_name = "Mafia_{}".format(name)
        try:
            everyone_perms = discord.PermissionOverwrite(send_messages=False)
            role_perms = discord.PermissionOverwrite(send_messages=True)
            role = await self.bot.create_role(ctx.message.server, name=game_name, hoist=True, mentionable=True)
            everyone = discord.ChannelPermissions(target=ctx.message.server.default_role, overwrite=everyone_perms)
            role_over = discord.ChannelPermissions(target=role, overwrite=role_perms)
            channel = await self.bot.create_channel(ctx.message.server, game_name, everyone, role_over)
        except discord.errors.HTTPException:
            await self.bot.say("Invalid name. Names must be alphanumeric with underscores and dashes.")
            return
        self.games[name] = MafiaGame(self.bot, channel, role, ctx.message.author, name)
        await self.bot.say("Mafia_{} created.".format(name))
        await self.bot.send_message(channel, ("Welcome to {0}." +
                                              "\nTo join, use `{1}joingame {2}`" +
                                              "\nGames in progress may not be joined." +
                                              "\n{3} may set the ruleset with {1}ruleset.")
                                    .format(game_name, self.bot.command_prefix, name, ctx.message.author.mention))

    @commands.command(pass_context=True)
    async def joingame(self, ctx, name: str):
        """Join a game of mafia. Enter the name of the game you want to enter. Games in progress can't be joined."""
        if ctx.message.author.id in self.members:
            await self.bot.say("You are already in a game.")
            return  # support for multiple games could be added in the future.
        try:
            game = self.games[name]
        except KeyError:
            await self.bot.say("Game not found.")
            return
        if game.state != '':
            await self.bot.say("Mafia_{} is already in session.".format(game.name))
            return
        member = MafiaMember(self.bot, ctx.message.author, game)
        self.members[ctx.message.author.id] = member
        game.members.append(member)
        await self.bot.add_roles(ctx.message.author, game.role)
        await self.bot.send_message(game.channel, "{} joined.".format(ctx.message.author.mention))

    @commands.group(pass_context=True, invoke_without_command=True)
    @in_game()
    @commands.check(lambda c: c.message.author == c.bot.get_cog("Mafia").members[c.message.author.id].game.leader)
    async def ruleset(self, ctx, ruleset: str):
        """Set the ruleset to be used."""
        await self.bot.say("Not yet implemented.")

    @commands.command(pass_context=True)
    @in_game()
    async def startgame(self, ctx):
        """Vote to start the game."""
        game = self.members[ctx.message.author.id].game
        if game.state != '':
            return
        if game.size < self.player_minimum:
            await self.bot.say("There needs to be {} members to start a game.".format(self.player_minimum))
            return
        self.members[ctx.message.author.id].vote = 'start'
        await self.bot.say("Votes to start: {}/{}".format(game.votes('start'), game.size))
        if game.votes('start') == game.size:
            await self.bot.say("Game is now in session.")
            await game.distribute_characters()
            await game.night()


def setup(bot):
    bot.add_cog(Mafia(bot))
