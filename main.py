import os
# from dotenv import load_dotenv

import discord
from discord.ext import tasks, commands
from discord import app_commands
from datetime import datetime, time as dt_time, timezone

# # Load .env variables
# load_dotenv()
# bot_token = os.getenv("BOT_TOKEN")
# guild_id_token = int(os.getenv("GUILD_ID_TOKEN"))

from keep_alive import keep_alive

keep_alive()

# using Replit's secret storage system
bot_token = os.environ["BOT_TOKEN"]
guild_id_token = int(os.environ["GUILD_ID_TOKEN"])

GUILD_OBJ = discord.Object(id=guild_id_token)

# Chore sets to rotate through
chore_sets = [[
    "Take out Trash and Recycling", "Take bins out on Tuesday",
    "Wash trash lid"
], ["Vacuum and Mop Floors"],
              ["Wash kitchen towels & bathmats", "Clean stovetop"],
              ["Sort mail from mailbox", "Clean kitchen counter and sink"]]

# In-memory assignment
member_assignments = {}

# Channel name to post assignments in
TARGET_CHANNEL_NAME = "chores"

################################
####### Custom Bot Class #######
################################


class ChorganizerBot(commands.Bot):

    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        intents.members = True

        super().__init__(command_prefix="!", intents=intents)

    async def setup_hook(self):
        synced = await self.tree.sync(
            guild=GUILD_OBJ)  # sync slash commands to specific guild
        print(f"Synced {len(synced)} commands to guild {GUILD_OBJ.id}!!")

    async def on_ready(self):
        print(f"{self.user} is ready!")
        print("-------------------------")

        # if not assign_chores.is_running():
        #     assign_chores.start()  # Start the weekly loop

    async def on_message(self, message):
        if message.author == self.user:
            return

        if message.content.lower().startswith(
                'hello') or message.content.lower().startswith('hi'):
            await message.channel.send(
                f'{message.author.mention}, Dont talk to me rn')

        if 'bye' in message.content.lower():
            await message.channel.send('Finally')

        await self.process_commands(message)  # Ensure commands still work

    async def on_guild_join(self, guild: discord.Guild):
        # Try to find a general-purpose channel to send the intro message
        default_channel = discord.utils.get(guild.text_channels,
                                            name="general")

        # If "general" doesn't exist, try the first available text channel
        if default_channel is None:
            for channel in guild.text_channels:
                if channel.permissions_for(guild.me).send_messages:
                    default_channel = channel
                    break

        if default_channel:
            await default_channel.send(
                "**🧽 Thanks for inviting me! I'm Chorganizer! 🧽**\n"
                "Here's how I can help you:\n"
                "• I automatically assign weekly chores to everyone in the server in a rotating basis!\n"
                "• Use `/mychore` to check your current chore.\n"
                "• I post chore assignments every week in the `#chores` channel.\n\n"
                "**🔧 Setup Tips:**\n"
                "• Make sure there's a text channel named `chores`, or create one!\n"
                "• To get started just give me a list of a set of chores you decide should be done by each person each week"
                "•• For example, [set1: [take out trash and recycling], set2: [Wash kitchen towels & bathmats, Clean stovetop], set3: [Sort mail from mailbox, Clean kitchen counter and sink]]"
                "•• Ideally, there should be an equal number of chore sets and housemates!"
                "• If you ever want to check your chore manually, just type `/mychore`.\n\n"
                "_Happy cleaning!_ ✨")


############################
#### Weekly Chore Loop #####
############################

from datetime import datetime, timezone, time as dt_time


@tasks.loop(time=dt_time(hour=17, minute=0))  # run 5pm UTC daily
async def assign_chores():
    now = datetime.now(timezone.utc)
    if now.weekday(
    ) != 2:  # Only run on Wednesday (Monday: 0, Tuesday: 1, Wednesday: 2, ...)
        return

    try:
        print(f"[{now}] Assigning chores...")

        for guild in client.guilds:
            channel = discord.utils.get(guild.text_channels,
                                        name=TARGET_CHANNEL_NAME)
            if not channel:
                print(
                    f"Channel '{TARGET_CHANNEL_NAME}' not found in guild '{guild.name}'"
                )
                continue

            members = sorted([m for m in guild.members if not m.bot],
                             key=lambda m: m.id)
            num_sets = len(chore_sets)

            # Get the number of weeks since a reference date (in our case we chose Jan 1, 2024)
            reference_date = datetime(2024, 1, 1, tzinfo=timezone.utc)
            weeks_since = (now - reference_date).days // 7

            # Rotate based on week number
            rotation = weeks_since % num_sets
            rotated_chore_sets = chore_sets[rotation:] + chore_sets[:rotation]

            message_lines = ["🧽 **Weekly Chore Assignments** 🧽\n"]

            num_members = len(members)
            for i in range(max(num_members, num_sets)):
                if i < num_members:  # if there are at least enough members as there are chore sets
                    member = members[i]
                    assigned_set = rotated_chore_sets[
                        i %
                        num_sets]  # guaranteed to have at least enough chores for all members due to check in start_cycle
                    assigned_chores = ", ".join(assigned_set)
                    message_lines.append(
                        f"**{member.display_name}** → {assigned_chores}")
                    member_assignments[member.id] = assigned_chores
                else:  # if there are more chore sets than there are members
                    # Extra chore sets with no one assigned
                    unassigned_chores = ", ".join(rotated_chore_sets[i])
                    message_lines.append(
                        f"**Unassigned** → {unassigned_chores}")
                    print(
                        f"⚠️ No member available for chore set {i}: {rotated_chore_sets[i]}"
                    )
            await channel.send("\n".join(message_lines))

    except Exception as e:
        print(f"❌ Error in assign_chores loop: {e}")


###########################
##### Slash Commands ######
###########################

client = ChorganizerBot()


@client.tree.command(name="mychore",
                     description="Check your current chore assignment",
                     guild=GUILD_OBJ)
async def my_chore(interaction: discord.Interaction):
    chore = member_assignments.get(interaction.user.id)
    if chore:
        await interaction.response.send_message(
            f"🧹 Your current chore is: **{chore}**")
    else:
        await interaction.response.send_message(
            "You haven't been assigned a chore yet.")


@client.tree.command(
    name="add_chores_set",
    description=
    "Add a set of comma-separated chores to the list of chore sets for me to assign and rotate regularly",
    guild=GUILD_OBJ)
async def add_chores(interaction: discord.Interaction, chores: str):
    global chore_sets, chore_cycle  # Access the global chore variables

    chore_set = [chore.strip() for chore in chores.split(',')]
    chore_sets.append(chore_set)  # update global chore_sets list

    await interaction.response.send_message(f"✅ Added chore set: {chore_set}")


@client.tree.command(
    name="start_chore_cycle",
    description="Start the weekly chore rotation (requires enough chore sets)",
    guild=GUILD_OBJ)
async def start_cycle(interaction: discord.Interaction):

    # Check if there are enough chore sets for the members in the guild
    for guild in client.guilds:
        members = [m for m in guild.members
                   if not m.bot]  # Get all non-bot members
        num_members = len(members)

        if num_members > len(
                chore_sets
        ):  # if there are more members than there are chore sets, dont start
            await interaction.response.send_message(
                f"❌ Error: There are {num_members} members, but only {len(chore_sets)} chore sets. Please add more chore sets before starting the cycle."
            )
            print(
                f"⚠️ Cannot start chore cycle: Not enough chore sets for {num_members} members!"
            )
            return  # Exit the function, preventing the cycle from starting

    if assign_chores.is_running():
        await interaction.response.send_message(
            "⚠️ Chore cycle is already running.")
    else:
        assign_chores.start()
        await interaction.response.send_message("✅ Starting chore cycle!")


@client.tree.command(
    name="stop_chore_cycle",
    description=
    "Stop the ongoing chores rotation. Warning: chores order may not resume if restarted after stopping",
    guild=GUILD_OBJ)
async def stop_cycle(interaction: discord.Interaction):
    if assign_chores.is_running():
        try:
            assign_chores.cancel()
            await interaction.response.send_message("🛑 Chore cycle stopped.")
        except Exception as e:
            await interaction.response.send_message(
                f"⚠️ Failed to stop chore cycle: {e}")
    else:
        await interaction.response.send_message(
            "ℹ️ Chore cycle is not currently running.")


#########################
###### Run the Bot ######
#########################

client.run(bot_token)
