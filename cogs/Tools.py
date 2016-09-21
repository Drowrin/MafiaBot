import traceback
import discord
import inspect
from discord.ext import commands


def is_owner():
    """Decorator to allow a command to run only if it is called by the owner."""
    return commands.check(lambda ctx: ctx.message.author.id == ctx.bot.owner.id)


class Tools:
    def __init__(self, bot):
        self.bot = bot

    @commands.command(pass_context=True)
    @is_owner()
    async def debug(self, ctx, *, code: str):
        """Evaluates an expression to see what is happening internally."""
        code = code.strip('` ')
        python = '```py\n{}\n```'

        env = {
            'bot': self.bot,
            'ctx': ctx,
            'message': ctx.message,
            'server': ctx.message.server,
            'channel': ctx.message.channel,
            'author': ctx.message.author
        }

        env.update(globals())

        try:
            result = eval(code, env)
            if inspect.isawaitable(result):
                result = await result
        except Exception:
            await self.bot.say(python.format(traceback.format_exc()))
            return

        await self.bot.say(python.format(result))

    @commands.command(pass_context=True, aliases=('exec',))
    @is_owner()
    async def execute(self, ctx, *, code: str):
        """Evaluates an expression to see what is happening internally."""
        code = code.strip('` ')
        python = '```py\n{}\n```'

        env = {
            'bot': self.bot,
            'ctx': ctx,
            'message': ctx.message,
            'server': ctx.message.server,
            'channel': ctx.message.channel,
            'author': ctx.message.author
        }

        env.update(globals())

        # noinspection PyBroadException
        try:
            exec(code, env)
            await self.bot.say('\N{OK HAND SIGN}')
        except Exception:
            await self.bot.say(python.format(traceback.format_exc()))


def setup(bot):
    bot.add_cog(Tools(bot))
