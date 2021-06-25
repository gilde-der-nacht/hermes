# Hermes

Service which allows several web clients to read and write message to a channel on a discord server. The service consists of two parts:

- A discord bot, which can read and write messages to a Discord server
- A web server which allows clients to connect to, via WebSocket

## Try It First

- `docker-compose up`
- `firefox http://127.0.0.1:8004/demo`

## Remote Docker

`DOCKER_HOST="ssh://user@domain:port" docker-compose up`

## Terms

Throughout the rest of this documents the two following terms are used:

- web-user: A user with an web browser
- discord-user: A user registered on Discord, can use any Discord client

## Environment

The environment variables for the service are stored in the `.env` file. This file is not added to the repository. As a reference the file `env-local` (for development on localhost) or `env-template` is good starting point.

- `WEB_STATUS_USERNAME`/`WEB_STATUS_PASSWORD`: Username and password for the protected `/status` page.
- `DISCORD_TOKEN`: Every Discord bot has a unique, secret token which is normally generated once, when a new bot is created. See below in section *Create Bot*.
- `PORT`: The port the web-service listens to. The web-service supports only HTTP, no HTTPS. Therefore it is advised to e.g. use a reverse proxy to offer HTTPS. The reverse proxy must be configured to allow WebSocket connections.

The following variables are only used for the `/demo` example. If the demo is not used, they may be left empty.

- `DEMO_WEBSOCKET_SERVER`: The URL where the WebSocket has to connect to. Normally something like wss://domainname.tld/ws, for development just ws://127.0.0.1/ws
- `DEMO_DISCORD_SERVERID`: Every Discord server has a unique id. See inside Discord: Server Settings -> Widgets -> Server ID.
- `DEMO_DISCORD_CHANNELID`: Unique ID of the Discord channel the message from the web-user has to be sent to. The Devloper Mode in the Discord Settings allows to copy the ID of every channel within Discord itself. See User Settings -> Advanced -> Develop Mode.

## Create Bot (Developer)

The service needs a Discord token to properly register as a Discord bot.

https://discord.com/developers/applications/

- New Application
- Bot / Add Bot
- Click to Reveal Token
- Add the Token to the environment of the service

## Add Bot (Server Administrator)

To add the Discord bot to a Discord Server, the administrator of the Discord server has to add the bot manually and give the bot appropriate permissions. The default permission can be created with combination of numeric values:

Permission Flag Examples

- Administrator = `8`
- Send Messages = `2048`
- Send Messages & Read Message History = `67584`
- Send Messages & Read Message History & Add Reactions = `67648`

https://discordapp.com/oauth2/authorize?&client_id=APPLICATION_ID&scope=bot&permissions=PERMISSION

Hermes Application ID = 814141033234300969

https://discordapp.com/oauth2/authorize?&client_id=814141033234300969&scope=bot&permissions=2048

## URLs Web Service

- `/`: Short text message to check if the server is running.
- `/ws`: URL the WebSocket has to connect to.
- `/status`: Gives information about web-users and Discord state. Password protected.
- `/demo`: A bare minimum demonstration for a web-user.

## Docker

`python:3.9-alpine3.13` probably would be a better fit as base image, but `pip` wants to build a package which needs gcc (available via package `build-base`) which leads to a quite large image (> 200 MByte). Needs further investigations.
