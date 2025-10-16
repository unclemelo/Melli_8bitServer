import discord
import subprocess
import os
import sys
from datetime import datetime
from discord import app_commands
from discord.ext import commands
from functools import wraps
from util.command_checks import is_command_enabled
from colorama import Fore, Style, init

# Initialize colorama for colored terminal output
init(autoreset=True)

# Developer IDs
devs = {667032667732312115, 954135885392252940, 1186435491252404384} 

def is_dev():
    """Decorator to restrict commands to developers."""
    def predicate(func):
        @wraps(func)
        async def wrapper(self, interaction: discord.Interaction, *args, **kwargs):
            if interaction.user.id in self.devs:
                return await func(self, interaction, *args, **kwargs)
            await interaction.response.send_message(
                "This command is restricted to developers.", ephemeral=True
            )
        return wrapper
    return predicate

class Updater(commands.Cog):
    """Cog for managing system-level commands like restarting and updating the bot."""
    UPDATE_CHANNEL_ID = 1308048388637462558

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.start_time = datetime.utcnow()
        self.bot.tree.on_error = self.on_tree_error
        self.devs = devs

    async def on_tree_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        """Handles errors occurring in app commands."""

        # 🕒 Handle CommandOnCooldown separately
        if isinstance(error, app_commands.CommandOnCooldown):
            await interaction.response.send_message(
                f"⌛ Command is on cooldown. Try again in {error.retry_after:.2f} seconds.",
                ephemeral=True
            )
            return

        # 🚫 Handle MissingPermissions cleanly
        if isinstance(error, app_commands.MissingPermissions):
            await interaction.response.send_message(
                "🚫 You lack the necessary permissions for this command.",
                ephemeral=True
            )
            return

        # ⚠️ Handle wrapped Forbidden errors (like timeout without permission)
        if isinstance(error, app_commands.CommandInvokeError) and isinstance(error.__cause__, discord.Forbidden):
            await interaction.response.send_message(
                "⚠️ I don't have permission to perform that action.",
                ephemeral=True
            )
            print(f"{Fore.RED}[FORBIDDEN]{Fore.WHITE} {error.__cause__}")
            return

        # 🧼 Fallback for all other errors
        try:
            if not interaction.response.is_done():
                await interaction.response.send_message(
                    "❌ An unexpected error occurred. Check the console logs for details.",
                    ephemeral=True
                )
        except discord.HTTPException:
            pass

        # 📜 Log nicely to console
        import traceback
        trace_text = ''.join(traceback.format_exception(type(error), error, error.__traceback__))
        print(
            f"\n{Fore.RED}{Style.BRIGHT}[TREE ERROR] {Fore.YELLOW}{type(error).__name__}\n"
            f"{Fore.CYAN}User: {Fore.WHITE}{interaction.user} ({interaction.user.id})\n"
            f"{Fore.CYAN}Command: {Fore.WHITE}{interaction.command.name if interaction.command else 'Unknown'}\n"
            f"{Fore.CYAN}Guild: {Fore.WHITE}{interaction.guild.name if interaction.guild else 'DMs'}\n"
            f"{Fore.MAGENTA}Traceback:\n{Fore.WHITE}{trace_text}"
        )

    def get_update_channel(self) -> discord.TextChannel:
        """Fetches the update channel."""
        return self.bot.get_channel(self.UPDATE_CHANNEL_ID)

    async def notify_updates(self, update_results: dict):
        """Sends update notifications to the designated update channel."""
        channel = self.get_update_channel()
        if not channel:
            print(f"{Fore.RED}[ERROR]{Fore.WHITE} Update channel not found.")
            return

        embed = discord.Embed(
            title="Bot Updated",
            description="Successfully pulled updates from GitHub and restarted.",
            color=0x3474eb,
            timestamp=datetime.utcnow()
        )

        git_response = update_results.get("git_pull", "No Git response available.")
        embed.add_field(
            name="GitHub Status",
            value=("No updates found. The bot is running the latest version."
                   if "Already up to date." in git_response else
                   "Updates applied. Check the [GitHub Page](<https://github.com/unclemelo/Melli>)"),
            inline=False
        )
        await channel.send(embed=embed)

    @staticmethod
    def restart_bot():
        """Restarts the bot using the current Python interpreter."""
        os.execv(sys.executable, [sys.executable] + sys.argv)

    @staticmethod
    def run_command(command: list) -> str:
        """Runs a shell command and returns the output."""
        try:
            result = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            return result.stdout if result.returncode == 0 else result.stderr
        except Exception as e:
            return str(e)
    
    def update_code(self) -> dict:
        """Pulls the latest code from GitHub and updates dependencies."""
        return {
            "update_server": self.run_command(["sudo", "apt", "update", "&&", "sudo", "apt", "upgrade"]),
            "git_pull": self.run_command(["git", "pull"]),
            "pip_install": self.run_command(["python3", "-m", "pip", "install", "-r", "requirements.txt"])
        }

    @app_commands.command(name="update", description="Developer Only")
    @is_dev()
    @app_commands.guilds()
    async def restart_cmd(self, interaction: discord.Interaction):
        """Command to update the bot and pull updates from GitHub."""
        embed = discord.Embed(
            title="Updating...",
            description="Pulling updates from GitHub & Ubuntu and restarting.",
            color=discord.Color.magenta()
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

        update_results = self.update_code()
        await self.notify_updates(update_results)

        git_response = update_results.get("git_pull", "No Git response available.")
        embed.description += "\n\nNo updates found. Cancelling the reboot..." if "Already up to date." in git_response else "\n\n🔧 Updates applied successfully."
        
        await interaction.followup.send(embed=embed, ephemeral=True)
        if "Already up to date." in git_response:
            pass
        else:
            print(f"{Fore.GREEN}[SYSTEM]{Fore.WHITE} Rebooting bot...")
            self.restart_bot()

async def setup(bot: commands.Bot):
    """Adds the Updater cog to the bot."""
    await bot.add_cog(Updater(bot))
