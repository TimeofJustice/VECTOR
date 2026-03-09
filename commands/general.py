import discord

from commands.registry import command_registrar


@command_registrar
def register_general_commands(bot: discord.Bot) -> None:
    @bot.slash_command(description='Sagt Hallo mit optionalem Namen.')
    async def hello(ctx: discord.ApplicationContext, name: str = None):
        target_name = name or ctx.author.name
        await ctx.respond(f'Hello {target_name}!')

    @bot.user_command(name='Say Hello')
    async def hi(ctx: discord.ApplicationContext, user: discord.User):
        await ctx.respond(f'{ctx.author.mention} says hello to {user.name}!')
