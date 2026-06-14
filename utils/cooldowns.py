# Copyright (c) 2026 Jonas Oelschner
# Licensed under the MIT License. See LICENSE in the project root.

from collections.abc import Callable

from discord.ext.commands import BucketType, Cooldown, dynamic_cooldown, max_concurrency


def _cooldown(
    seconds: float = 0,
    minutes: float = 0,
    hours: float = 0,
    by_pass_by_admins: bool = True,
) -> Callable:
    """Apply a per-user cooldown to an application command.

    The duration is the sum of ``seconds``, ``minutes`` and ``hours``. When
    ``by_pass_by_admins`` is True, guild administrators are never rate-limited.
    """
    total_seconds = seconds + (minutes * 60) + (hours * 3600)

    def factory(ctx) -> Cooldown | None:
        # `dynamic_cooldown` calls this per invocation with the ApplicationContext.
        # Returning None bypasses the cooldown for this invocation.
        if by_pass_by_admins:
            perms = getattr(getattr(ctx, "author", None), "guild_permissions", None)
            if perms is not None and perms.administrator:
                return None

        return Cooldown(1, total_seconds)

    return dynamic_cooldown(factory, BucketType.user)


def _max_concurrency(number: int = 1, *, wait: bool = False) -> Callable:
    """Limit how many invocations of a command run at once per guild."""
    return max_concurrency(number, per=BucketType.guild, wait=wait)


def throttle(
    seconds: float = 0,
    minutes: float = 0,
    hours: float = 0,
    by_pass_by_admins: bool = True,
    concurrency: int | None = None,
    wait: bool = False,
) -> Callable:
    """Combine a per-user cooldown and a per-guild concurrency limit in one decorator.

    - A cooldown is applied when any of ``seconds``/``minutes``/``hours`` is set
      (admins bypass it when ``by_pass_by_admins`` is True).
    - A per-guild concurrency limit is applied when ``concurrency`` is set; ``wait``
      controls whether extra invocations queue (True) or are rejected (False).

    Place directly above the command function, BELOW the command decorator
    (`@bot.slash_command` / `@bot.user_command` / `@bot.message_command` /
    group subcommand).
    """

    def decorator(func: Callable) -> Callable:
        if seconds or minutes or hours:
            func = _cooldown(
                seconds=seconds,
                minutes=minutes,
                hours=hours,
                by_pass_by_admins=by_pass_by_admins,
            )(func)

        if concurrency is not None:
            func = _max_concurrency(concurrency, wait=wait)(func)

        return func

    return decorator
