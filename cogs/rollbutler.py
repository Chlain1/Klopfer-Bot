import discord
from discord.ext import commands
from discord.ext.commands import Context
import random


class RollModal(discord.ui.Modal):
    def __init__(self, dice_sides: int):
        super().__init__(title=f"Roll D{dice_sides}")
        self.dice_sides = dice_sides
        
        self.rolls_input = discord.ui.TextInput(
            label="Number of rolls",
            placeholder="Enter number of rolls (1-100)",
            default="1",
            min_length=1,
            max_length=3
        )
        self.add_item(self.rolls_input)
    
    async def on_submit(self, interaction: discord.Interaction):
        try:
            times = int(self.rolls_input.value)
        except ValueError:
            await interaction.response.send_message("Please enter a valid number.", ephemeral=True)
            return
        
        if times > 100 or times < 1:
            await interaction.response.send_message("You can only roll between 1 and 100 times.", ephemeral=True)
            return
        
        embed = discord.Embed(
            title=f"Rolling a D{self.dice_sides} {times} time{'s' if times != 1 else ''}",
            colour=0xFC0FC0,
            description=""
        )
        
        sum = 0
        for i in range(times):
            roll_result = random.randint(1, self.dice_sides)
            embed.description += f"Roll {i + 1}: {roll_result}\n"
            sum += roll_result
        embed.description += f"Sum of the rolls: {sum}\n"
        
        await interaction.response.send_message(embed=embed)


class DiceSelect(discord.ui.Select):
    def __init__(self):
        options = [
            discord.SelectOption(label="D4", description="4-sided dice", value="4"),
            discord.SelectOption(label="D6", description="6-sided dice", value="6"),
            discord.SelectOption(label="D8", description="8-sided dice", value="8"),
            discord.SelectOption(label="D10", description="10-sided dice", value="10"),
            discord.SelectOption(label="D12", description="12-sided dice", value="12"),
            discord.SelectOption(label="D20", description="20-sided dice", value="20"),
            discord.SelectOption(label="D100", description="100-sided dice", value="100"),
        ]
        
        super().__init__(placeholder="Choose a dice type...", min_values=1, max_values=1, options=options)
    
    async def callback(self, interaction: discord.Interaction):
        dice_sides = int(self.values[0])
        modal = RollModal(dice_sides)
        await interaction.response.send_modal(modal)


class DiceView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=300)
        self.add_item(DiceSelect())
    
    async def on_timeout(self):
        for item in self.children:
            item.disabled = True


# Here we name the cog and create a new class for the cog.
class RollButler(commands.Cog, name="rollbutler"):
    def __init__(self, bot) -> None:
        self.bot = bot

    # Here you can just add your own commands, you'll always need to provide "self" as first parameter.

    @commands.hybrid_command(
        name="roll",
        description="This command lets you roll a dice as often as you specify.",
    )
    async def roll(self, context: Context) -> None:
        """
        Roll dice using a dropdown menu to select dice type and a modal for number of rolls.

        :param context: The application command context.
        """
        embed = discord.Embed(
            title="🎲 Dice Roller",
            description="Select a dice type from the dropdown below to get started!",
            colour=0xFC0FC0
        )
        
        view = DiceView()
        await context.send(embed=embed, view=view)



# And then we finally add the cog to the bot so that it can load, unload, reload and use it's content.
async def setup(bot) -> None:
    await bot.add_cog(RollButler(bot))
