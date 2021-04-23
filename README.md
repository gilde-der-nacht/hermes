# Hermes

Service which allows web client to talk to a discord server. The service consists of two parts:

- A discord bot, which can listen and write messages to a Discord server
- A web server which allows clients to connect to, via WebSocket

## Terms

Throughout the rest of this documents the two following terms are used:

web-user: A user with an web browser
discord-user: A user registered on Discord

## Create Bot (Developer)

The service needs a special Discord token to register as a Discord bot.

https://discord.com/developers/applications/

- New Application
- Bot / Add Bot
- Click to Reveal Token
- Add the Token to the environment of the service

## Add Bot (Server Administrator)

To add the Discord bot to a specific Discord Server, the administrator the Discord server has to add the bot and give appropriate permissions. The default permission is created with combination of numeric values

Permission Flag
- Administrator = `8`
- Send Messages = `2048`
- Send Messages & Read Message History = `67584`
- Send Messages & Read Message History & Add Reactions = `67648`

https://discordapp.com/oauth2/authorize?&client_id=APPLICATION_ID&scope=bot&permissions=PERMISSION

https://discordapp.com/oauth2/authorize?&client_id=TODO&scope=bot&permissions=2048

## Environment

TODO

- `WEB_STATUS_USERNAME`: TODO
- `WEB_STATUS_PASSWORD`: TODO
- `DISCORD_TOKEN`: TODO
- `PORT`: TODO

TODO

- `DEMO_WEBSOCKET_SERVER`: TODO
- `DEMO_DISCORD_SERVERID`: TODO
- `DEMO_DISCORD_CHANNEL`: TODO

## Docker

`python:3.9-alpine3.13` probably would be a better fit, but pip wants to build a package which needs gcc (available via package `build-base`) which leads to a quite large image (> 200 MByte). Needs further investigations.

## Ideas

- Bot adds and emoji to every message delivered correctly to all web-users
- Message within discord for every connected/disconnected user
- 1:1 chats?
- Detect spam from web-users
