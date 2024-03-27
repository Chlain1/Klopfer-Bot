import discord
import time
import config
from config import token, link, prefix, ownerid
from discord.ext import commands
from discord.utils import get

intents = discord.Intents.default()
intents.message_content = True

client = commands.Bot(command_prefix=prefix, intents=intents)

@client.event
async def on_ready():
    print("----------------------")
    print("Logged In As")
    print("Username: %s"%client.user.name)
    print("ID: %s"%client.user.id)
    print("----------------------")

@client.command()
async def ping():
    '''See if The Bot is Working'''
    pingtime = time.time()
    pingms = await client.say("Pinging...")
    ping = time.time() - pingtime
    await client.edit_message(pingms, ":ping_pong:  time is `%.01f seconds`" % ping)
client.add_command(ping)
    
@client.command()
async def botinvite():
    '''A Link To Invite This Bot To Your Server!'''
    await client.say("Check Your Dm's :wink:")
    await client.whisper(link)
client.add_command(botinvite)

# The command to do the klopf

@client.command()
async def klopf():
    '''a person is doing the klopf'''
    user_roles = [r.name.lower() for r in ctx.message.author.roles]
    if "Klopfer-Teilnehmer" not in user_roles:
        return await client.say("Du nimmst noch nicht teil, nimm teil mit kjoin um Klopfen zu können.")
    else:
        currentTime = datetime.now().strftime(r"%I:%M %p")
        legalTime = ["12:12 AM", "01:01 AM", "02:02 AM", "03:03 AM", "04:04 AM", "05:05 AM", "06:06 AM", "07:07 AM",
                     "08:08 AM", "09:09 AM", "10:10 AM", "11:11 AM", "12:12 PM", "01:01 PM", "02:02 PM", "03:03 PM",
                     "04:04 PM", "05:05 PM", "06:06 PM", "07:07 PM", "08:08 PM", "09:09 PM", "10:10 PM", "11:11 PM"]
        if currentTime in legalTime:
            return await client.say("Gut gemacht! Du hast richtig geklopft")
        else:
            return await client.say("Duu H*** hast falsch geklopft")
client.add_command(klopf)


# The command to join the klopf

@client.command()
async def kjoin():
    '''a person wants to join the klopf'''
    user_roles = [r.name.lower() for r in ctx.message.author.roles]

    if "Klopfer-Teilnehmer" not in user_roles:
        member = ctx.message.author
        role = get(member.server.roles, name="Klopfer-Teilnehmer")
        await bot.add_roles(member, role)
        return await client.say(ctx.message.author + " nimmt nun teil!")
    else:
        return await client.say("Du nimmst doch schon teil!")
client.add_command(kjoin)


client.run(token)
