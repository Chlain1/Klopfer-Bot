# Python Klopfer Bot

<p align="center">
  <a href="https://codecov.io/gh/Chlain1/Klopfer-Bot">
    <img src="https://codecov.io/gh/Chlain1/Klopfer-Bot/branch/main/graph/badge.svg" alt="Coverage">
  </a>
  <a href="https://discord.com/oauth2/authorize?client_id=1222645997151326259">
    <img src="" alt="Install to Discord Server">
  </a>
</p>

<!-- TODO: Add Install Image source anything -->


## Disclaimer

Slash commands can take some time to get registered globally, so if you want to test a command you should use
the `@app_commands.guilds()` decorator so that it gets registered instantly. Example:

```py
@commands.hybrid_command(
  name="command",
  description="Command description",
)
@app_commands.guilds(discord.Object(id=GUILD_ID)) # Place your guild ID here
```

### `config.json` file

There is [`config.json`](config.json) file where you can put the
needed things to edit.

Here is an explanation of what everything is:

| Variable                  | What it is                                     |
| ------------------------- | ---------------------------------------------- |
| YOUR_BOT_PREFIX_HERE      | The prefix you want to use for normal commands |
| YOUR_BOT_INVITE_LINK_HERE | The link to invite the bot                     |

### `.env` file

To set up the token you will have to either make use of the [`.env.example`](.env) file, either copy or rename it to `.env` and replace `YOUR_BOT_TOKEN_HERE` with your bot's token.

Alternatively you can simply create an environment variable named `TOKEN`.

## How to start

To start the bot you simply need to launch, either your terminal (Linux, Mac & Windows), or your Command Prompt (
Windows)
.

Before running the bot you will need to install all the requirements with this command:

```
python -m pip install -r requirements.txt
```

After that you can start it with

```
python bot.py
```

> **Note** You may need to replace `python` with `py`, `python3`, `python3.11`, etc. depending on what Python versions you have installed on the machine.



## Built With

- [Python 3.14.2](https://www.python.org/)

## Based on

This Bot was build on the Template from kkrypt0nn
- [Bot-Template Github](https://github.com/kkrypt0nn/Python-Discord-Bot-Template)

