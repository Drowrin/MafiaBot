import random
import json
from enum import Enum
from collections import Counter
import discord
from discord.ext import commands


with open('mafia.json') as f:
    mafia_content = json.load(f)


Character = Enum('Character', mafia_content['characters'])


class MafiaMember:
    def __init__(self, bot: commands.Bot, member: discord.Member, game):
        self.bot = bot
        self.member = member
        self.game = game
        self.character = None  # this will be set when the game starts
        self.vote = ""
        self.alive = True

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
        self.ruleset = mafia_content['rulesets']['default'].split()
        self.state = ''

    @property
    def size(self):
        return len(self.members)

    @property
    def unassigned_members(self):
        return [m for m in self.members if m.character is None]

    def get_characters(self, character: Character):
        """Get all the members of a specific character."""
        return [m for m in self.members if m.character == character]

    def get_member_named(self, name: str):
        if name not in [m.member.display_name for m in self.members]:
            raise KeyError
        return [m for m in self.members if m.member.display_name == name][0]

    def votes(self, v: str):
        return len([m for m in self.members if m.vote == v])

    def clear_votes(self):
        for m in self.members:
            m.vote = ''

    async def message(self, character: Character, s: str, omit: discord.Member=None):
        """Send a message to all members of a specific character."""
        for m in [x for x in self.get_characters(character) if x.member != omit]:
            await m.message(s)

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
        self.message(Character.mafia, "Members of team mafia:\n{}".format(
            '\n'.join([m.member.display_name for m in self.get_characters(Character.mafia)])))

    async def night(self):
        self.state = 'night'
        self.clear_votes()
        for m in self.get_characters(Character.innocent):
            # innocents take no action, so they automatically vote.
            m.vote = 'day'
        await self.bot.send_message(self.channel, "It is now night." +
                                    "\nThe game will progress to morning once all characters perform their action.")

    async def day(self):
        if all([m.vote != '' for m in self.members]):
            self.state = 'day'
            self.clear_votes()
            message = ["It is now day."]
            mafia_pick = Counter([m.vote for m in self.get_characters(Character.mafia)]).most_common(1)[0][0]
            victim = self.get_member_named(mafia_pick)
            saved = any([m.vote == mafia_pick for m in self.get_characters(Character.doctor)])
            if saved:
                message.append("An attempt was made on {}'s life, but they were saved.".format(victim.member.mention))
            else:
                victim.alive = False
                message.append("{} was killed.".format(victim.member.mention))
                if len([m for m in self.members if m.character == Character.mafia]) >= (len(self.members) / 2):
                    await self.bot.say('\n'.join(message))
                    await self.endgame(True)
            message.append("Now it is time to discuss. When you are ready to vote, use %vote <name>.")
            message.append("If you want to vote anonymously, DM the command to me.")
            await self.bot.send_message(self.channel, '\n'.join(message))

    async def lynch(self):
        if all([m.vote != '' for m in self.members]):
            self.state = 'lynch'
            self.clear_votes()
            message = ['The vote is over.']
            target_name = Counter([m.vote for m in self.members]).most_common(1)[0][0]
            target = self.get_member_named(target_name)
            message.append('{} has been lynched.'.format(target_name))
            target.alive = False
            await self.bot.send_message(self.channel, '\n'.join(message))
            if not any(m.character == Character.mafia for m in self.members):
                await self.endgame(False)
            else:
                await self.night()

    async def endgame(self, mafia_win: bool):
        message = ["Mafia Win!" if mafia_win else "Innocents Win!", "Who was who:"]
        for m in self.members:
            message.append("{} -- {}".format(m.member.display_name, m.character.name))
        message.append("\nThe game is over. This channel will remain as a record until deleted.")
        await self.bot.send_message(self.channel, '\n'.join(message))
        await self.bot.delete_role(self.channel.server, self.role)


def get_game(ctx) -> MafiaGame:
    return ctx.bot.get_cog("Mafia").members[ctx.message.author.id].game


def is_character(character: Character):
    def char_check(ctx):
        mafia = ctx.bot.get_cog("Mafia")
        if not ctx.message.channel.is_private:
            # if someone calls help, it would reveal what actions they have access to and reveal their character
            # so, we only allow this check to pass in private messages
            return False
        if ctx.message.author.id not in mafia.members:
            return False
        if mafia.members[ctx.message.author.id].character != character:
            return False
        if mafia.members[ctx.message.author.id].alive:
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


def state(s):
    """Check that the game is in this state."""
    return commands.check(lambda ctx: get_game(ctx).state == s)


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

    # noinspection PyUnusedLocal
    @commands.group(pass_context=True, invoke_without_command=True)
    @in_game()
    @commands.check(lambda ctx: ctx.message.author == get_game(ctx).leader)
    async def ruleset(self, ctx, ruleset: str):
        """Set the ruleset to be used."""
        await self.bot.say("Not yet implemented. (currently only one ruleset)")

    @commands.command(pass_context=True)
    @in_game()
    @state('')
    async def startgame(self, ctx):
        """Vote to start the game."""
        game = self.members[ctx.message.author.id].game
        if game.size < self.player_minimum:
            await self.bot.say("There needs to be {} members to start a game.".format(self.player_minimum))
            return
        self.members[ctx.message.author.id].vote = 'start'
        await self.bot.say("Votes to start: {}/{}".format(game.votes('start'), game.size))
        if game.votes('start') == game.size:
            await self.bot.say("Game is now in session.")
            await game.distribute_characters()
            await game.night()

    @commands.command(pass_context=True)
    @state('day')
    async def vote(self, ctx, name: str):
        """Vote to lych someone. You can change your vote, but as soon as everyone has voted they are locked in."""
        game = get_game(ctx)
        try:
            target = game.get_member_named(name)
        except KeyError:
            await self.bot.say("{} not found.".format(name))
            return
        game.members[ctx.message.author.id].vote = target.member.display_name
        await self.bot.reply("Vote recorded \N{OK HAND SIGN}")
        await game.lynch()

    @commands.group(invoke_without_command=True)
    @is_character(Character.mafia)
    async def mafia(self):
        """Commands for mafia characters."""

    @mafia.command(pass_context=True)
    @is_character(Character.mafia)
    @state('night')
    async def speak(self, ctx, *, message):
        """Send a message to fellow mafia members. Only enabled at night."""
        author = ctx.message.author
        await get_game(ctx).message(Character.mafia, '{}: {}'.format(author.display_name, message), omit=author)

    @mafia.command(pass_context=True, name='vote')
    @is_character(Character.mafia)
    @state('night')
    async def mafia_vote(self, ctx, *, name):
        """Vote for a member to be killed.

        You may change your vote, but once all players have taken action votes are locked in."""
        game = get_game(ctx)
        try:
            target = game.get_member_named(name)
        except KeyError:
            await self.bot.say("{} not found.".format(name))
            return
        game.members[ctx.message.author.id].vote = target.member.display_name
        await self.bot.reply("Vote recorded \N{OK HAND SIGN}")
        await game.day()

    @commands.command(pass_context=True)
    @is_character(Character.detective)
    @state('night')
    async def investigate(self, ctx, name: str):
        """Investigate a player to find out who they are. Once per night."""
        game = get_game(ctx)
        if self.members[ctx.message.author.id].vote != '':
            await self.bot.say("That can only be used once per night.")
            return
        try:
            target = game.get_member_named(name)
        except KeyError:
            await self.bot.say("{} not found.".format(name))
            return
        game.members[ctx.message.author.id].vote = name
        await self.bot.say(target.character.name)

    @commands.command(pass_context=True)
    @is_character(Character.doctor)
    @state('night')
    async def save(self, ctx, name: str):
        game = get_game(ctx)
        try:
            target = game.get_member_named(name)
        except KeyError:
            await self.bot.say("{} not found.".format(name))
            return
        game.members[ctx.message.author.id].vote = target.member.display_name
        await self.bot.say("You are prepared to save {}.".format(name))


def setup(bot):
    bot.add_cog(Mafia(bot))
