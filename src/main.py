
import asyncio
import base64
import collections
import discord
import logging
import starlette
import starlette.applications
import starlette.config
import starlette.status
import time
import types
import uvicorn
import websockets

"""
Ideas:

- Register: Currently author and guildid and channelid, are sent with every
  message. A web-user see Discord message only after it send its own message
  first. Is it better idea to add a "register" message and register the user
  when he opens the web page?
- Delivered: Bot may add an emoji to every message in Discord, if a message is
  delivered to all web-users (await message.add_reaction('✅'))
- 1:1 Chats: For every web-user, there is a "room" within Discord, just for this
  web-user.
- Spam: Detect spam from web-users
- Starlette Basic Authetication: Is there a middleware available? Not just the
  example on starlette?
- Proper Discord Shutdown: Currently starlette reacts to Ctrl+C and as
  consequence this application is shut down, without properly shutting down
  discord
- Decoupling: At the moment the classes Gateway, Discord and Web are stroungly
  coupled. There is much room for improvment here.
"""

config = starlette.config.Config('.env')

DISCORD_TOKEN = config('DISCORD_TOKEN')
WEB_STATUS_USERNAME = config('WEB_STATUS_USERNAME')
WEB_STATUS_PASSWORD = config('WEB_STATUS_PASSWORD')

DEMO_WEBSOCKET_SERVER = config('DEMO_WEBSOCKET_SERVER')
DEMO_DISCORD_GUILDID = config('DEMO_DISCORD_GUILDID')
DEMO_DISCORD_CHANNELID = config('DEMO_DISCORD_CHANNELID')

ENABLE_FAKE_DISCORD = config('ENABLE_FAKE_DISCORD', cast=bool, default=False)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('hermes')

def dict2obj(d):
	"""
	d = {'a': 2}
	d['a']  # -> 2
	d.a  # AttributeError: 'dict' object has no attribute 'a'
	o = dict2obj(d)
	o.a  # -> 2
	"""
	return types.SimpleNamespace(**d)

# Web

"""
https://www.starlette.io/
"""

class Web:
	def __init__(self, gateway):
		self.gateway = gateway

	def root(self, request):
		"""
		$ curl http://127.0.0.1:8004
		"""
		return starlette.responses.PlainTextResponse('Up and Alive\n')

	def status(self, request):
		"""
		$ curl --silent --user admin:pw http://127.0.0.1:8004/status | jq
		"""
		RESPONSE_UNAUTHORIZED = starlette.responses.Response('', status_code=starlette.status.HTTP_401_UNAUTHORIZED, headers={'WWW-Authenticate': 'Basic realm=Status'})
		if 'Authorization' not in request.headers:
			return RESPONSE_UNAUTHORIZED
		try:
			authorization = request.headers['Authorization']
			scheme, credentials_encoded = authorization.split(' ', 2)
			assert scheme == 'Basic'
			credentials = base64.b64decode(credentials_encoded).decode('ascii')
			username, password = credentials.split(':', 2)
		except:
			return starlette.responses.Response('', status_code=starlette.status.HTTP_400_BAD_REQUEST)
		if (username != WEB_STATUS_USERNAME) or (password != WEB_STATUS_PASSWORD):
			return RESPONSE_UNAUTHORIZED

		runtime_seconds = int(time.time() - self.gateway.time_started)
		return starlette.responses.JSONResponse({
			'runtime_seconds': runtime_seconds,
			'web': self.info(),
			'discord': self.gateway.discord.info(),
		})

	def info(self):
		connected = []
		for connection in self.connections:
			host, port = connection.websocket.client.host, connection.websocket.client.port
			headers = connection.websocket.headers
			connected.append({
				'host': host,
				'port': port,
				'headers': { name:headers[name] for name in headers },
				'author': connection.author,
				'channelid': connection.channelid,
			})
		return {
			'connected': connected,
			'count_connections': self.count_connections,
		}


	def demo(self, request):
		html = open('demo.html', 'r').read()
		html = html.replace('DEMO_WEBSOCKET_SERVER', DEMO_WEBSOCKET_SERVER)
		html = html.replace('DEMO_DISCORD_GUILDID', DEMO_DISCORD_GUILDID)
		html = html.replace('DEMO_DISCORD_CHANNELID', DEMO_DISCORD_CHANNELID)
		return starlette.responses.HTMLResponse(html)

	async def handle_message(self, connection, message):
		"""
		$ wget https://github.com/vi/websocat/releases/download/v1.8.0/websocat_amd64-linux
		$ echo '{"type":"ping"}' | ./websocat_amd64-linux --one-message --no-close ws://127.0.0.1:8004/ws
		"""

		if message.type == 'ping':
			await connection.websocket.send_json({'type': 'pong'})
		elif message.type == 'text':
			if connection.guildid is None:
				connection.guildid, connection.channelid, connection.author = int(message.guildid), int(message.channelid), message.author
				text = '**' + connection.author + '**: *Connected*'
				await self.gateway.discord.send_message(connection.guildid, connection.channelid, text)
			text = '**' + message.author + '**: ' + message.text
			await self.gateway.discord.send_message(connection.guildid, connection.channelid, text)

	async def websocket(self, websocket):
		await websocket.accept()
		connection = dict2obj({
			'websocket': websocket,
			'author': '',
			'guildid': None,
			'channelid': None,
		})
		self.connections.append(connection)
		self.count_connections[websocket.client.host] += 1
		try:
			while True:
				message = dict2obj(await websocket.receive_json())
				await self.handle_message(connection, message)
		except starlette.websockets.WebSocketDisconnect:
			pass
		except websockets.exceptions.ConnectionClosedOK:
			pass
		self.connections.remove(connection)
		text = '**' + connection.author + '**: *Disconnected*'
		await self.gateway.discord.send_message(connection.guildid, connection.channelid, text)

	async def start(self):
		self.count_connections = collections.defaultdict(lambda: 0)
		self.connections = []
		routes = [
			starlette.routing.Route('/', self.root),
			starlette.routing.Route('/demo', self.demo),
			starlette.routing.Route('/status', self.status),
			starlette.routing.WebSocketRoute('/ws', self.websocket),
		]
		app = starlette.applications.Starlette(debug=False, routes=routes)
		config = uvicorn.Config(app=app, port=8004, host='0.0.0.0')  # if executed through Docker, change the port in the Docker configuration
		server = uvicorn.Server(config)
		await server.serve()

# Discord

"""
https://discordpy.readthedocs.io/en/stable/#manuals
https://discordpy.readthedocs.io/en/latest/api.html
"""

class Discord(discord.Client):
	def __init__(self, gateway):
		super().__init__()
		self.gateway = gateway

	async def start(self):
		await self.login(DISCORD_TOKEN)
		await self.connect()

	async def on_ready(self):
		logger.info('Discord: Ready')

	async def on_message(self, message):
		for connection in self.gateway.web.connections:
			if (message.guild.id == connection.guildid) and (message.channel.id == connection.channelid):
				# only send message from discord-user to a web-user, if the web-user has registered itself to a channel
				await connection.websocket.send_json({
					'type': 'text',
					'author': message.author.display_name,  # author.display_name != author.name
					'channel': message.channel.name,
					'text': message.content,
				})

	async def send_message(self, guildid, channelid, text):
		guild = discord.utils.get(self.guilds, id=guildid)
		if guild is None:
			logger.debug('Discord: guild {0} not found'.format(guildid))
			return
		channel = discord.utils.get(guild.channels, id=channelid)
		if type(channel) != discord.channel.TextChannel:
			logger.debug('Discord: channel {0} not found'.format(channelid))
			return
		await channel.send(text)

	def info(self):
		user = self.user.name
		return {
			'user': user,
		}

class FakeDiscord():
	"""
	Acts somewhat like the Discord class, without connecting to a Discord server
	"""

	def __init__(self, gateway):
		self.gateway = gateway

	async def start(self):
		asyncio.create_task(self._task())
		logger.info('FakeDiscord: Ready')

	async def send_message(self, guildid, channelid, text):
		await self._send_all(text)

	async def _send_all(self, text):
		for (i, connection) in enumerate(self.gateway.web.connections):
			await connection.websocket.send_json({
				'type': 'text',
				'author': 'FakeAuthor',
				'channel': 'FakeChannel',
				'text': text,
			})

	async def _task(self):
		while True:
			text = 'Time ' + str(int(time.time()))
			logger.debug('FakeDiscord: ' + text)
			await self._send_all(text)
			await asyncio.sleep(5.0)

	def info(self):
		return {'user': 'FakeUser'}

# Gateway

class Gateway:
	def __init__(self):
		self.time_started = time.time()
		self.web = Web(self)
		self.discord = FakeDiscord(self) if ENABLE_FAKE_DISCORD else Discord(self)

	def start(self):
		task_web = self.web.start()
		task_discord = self.discord.start()

		loop = asyncio.get_event_loop()
		loop.create_task(task_discord)
		# Intentionally only wait until starlette is not running anymore, because at the moment only starlette handles Ctrl+C
		loop.run_until_complete(task_web)

def start():
	gateway = Gateway()
	gateway.start()

start()
