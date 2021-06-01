
import asyncio
import base64
import collections
import discord
import starlette
import starlette.applications
import starlette.config
import starlette.status
import sys
import time
import types
import uvicorn
import websockets

"""

- TODO .env is at a different place in the docker image, should be done better
- TODO put functions for routes into namespace or class
- TODO decouple State/Discord/Starlette
- TODO replace starlette with FastAPI?
- TODO add a register message? instead of sending author, channel, ... everytime?

Ideas:

- Bot adds an emoji to every message delivered correctly to all web-users -> await message.add_reaction('✅')
- 1:1 chats?
- Detect spam from web-users

"""

config = starlette.config.Config('../.env')

DISCORD_TOKEN = config('DISCORD_TOKEN')
WEB_STATUS_USERNAME = config('WEB_STATUS_USERNAME')
WEB_STATUS_PASSWORD = config('WEB_STATUS_PASSWORD')

DEMO_WEBSOCKET_SERVER = config('DEMO_WEBSOCKET_SERVER')
DEMO_DISCORD_SERVERID = config('DEMO_DISCORD_SERVERID')
DEMO_DISCORD_CHANNELID = config('DEMO_DISCORD_CHANNELID')

def dict2obj(d): return types.SimpleNamespace(**d)

class State:
	def __init__(self):
		self.connections = []
		self.time_started = time.time()
		self.count_connections = collections.defaultdict(lambda: 0)
		self.discord = None

state = State()

async def task_timer(loop):
	"""
	TODO change this into a Discord fake emulation to test the service without Discord
	"""
	while True:
		print('Timer', 'connected#', len(state.connections))
		for (i, connection) in enumerate(state.connections):
			text = 'Hello From Server. You ID Is ' + str(i) + '. Time Is ' + str(time.time())
			await connection.websocket.send_json({'type': 'text', 'text': text})
		await asyncio.sleep(5.0, loop=loop)

"""
https://www.starlette.io/
"""

def root(request):
	"""
	$ curl http://127.0.0.1:8000
	"""
	return starlette.responses.PlainTextResponse('Up and Alive\n')

def status(request):
	"""
	$ curl --silent --user admin:pw http://127.0.0.1:8000/status | jq

	TODO add discord information, connected server, ...
	TODO is there a simpler middleware available? not just the example on starlette?
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

	runtime_seconds = int(time.time() - state.time_started)
	connected = []
	for connection in state.connections:
		host, port = connection.websocket.client.host, connection.websocket.client.port
		headers = connection.websocket.headers
		connected.append({
			'host': host,
			'port': port,
			'headers': { name:headers[name] for name in headers },
			'author': connection.author,
			'channel': connection.channel,
		})
	discord_user = state.discord.user.name if state.discord is not None else ''
	return starlette.responses.JSONResponse({
		'runtime': runtime_seconds,
		'connected': connected,
		'count_connections': state.count_connections,
		'discord_user': discord_user,
	})

def demo(request):
	html = open('demo.html', 'r').read()
	html = html.replace('DEMO_WEBSOCKET_SERVER', DEMO_WEBSOCKET_SERVER)
	html = html.replace('DEMO_DISCORD_SERVERID', DEMO_DISCORD_SERVERID)
	html = html.replace('DEMO_DISCORD_CHANNELID', DEMO_DISCORD_CHANNELID)
	return starlette.responses.HTMLResponse(html)

async def handle_message(connection, message):
	if message.type == 'ping':
		await connection.websocket.send_json({'type': 'pong'})
	elif message.type == 'text':
		if connection.serverid is None:
			connection.serverid, connection.channelid, connection.author = message.serverid, message.channelid, message.author
			text = '**' + connection.author + '**: *Connected*'
			await state.discord.send_message(connection.serverid, connection.channelid, text)
		text = '**' + message.author + '**: ' + message.text
		await state.discord.send_message(message.serverid, message.channelid, text)

async def websocket(websocket):
	if state.discord is None:
		return
	await websocket.accept()
	connection = dict2obj({
		'websocket': websocket,
		'author': '',
		'serverid': None,
		'channelid': None,
	})
	state.connections.append(connection)
	state.count_connections[websocket.client.host] += 1
	try:
		while True:
			message = dict2obj(await websocket.receive_json())
			#print('message', message)
			await handle_message(connection, message)
	except starlette.websockets.WebSocketDisconnect:
		pass
	except websockets.exceptions.ConnectionClosedOK:
		pass
	except Exception as e:
		print(e)
		# TODO add to statistics?
	if state.discord is not None:
		pass
	if connection.serverid is not None:
		text = '**' + connection.author + '**: *Disconnected*'
		await state.discord.send_message(connection.serverid, connection.channelid, text)
	state.connections.remove(connection)

async def task_web(loop):
	routes = [
		starlette.routing.Route('/', root),
		starlette.routing.Route('/demo', demo),
		starlette.routing.Route('/status', status),
		starlette.routing.WebSocketRoute('/ws', websocket),
	]
	app = starlette.applications.Starlette(debug=True, routes=routes)
	config = uvicorn.Config(app=app, loop=loop, port=8000, host='0.0.0.0')  # if executed through Docker, change the port in the Docker configuration
	server = uvicorn.Server(config)
	await server.serve()

"""
https://discordpy.readthedocs.io/en/stable/#manuals
https://discordpy.readthedocs.io/en/latest/api.html
"""

class MyClient(discord.Client):
	async def on_ready(self):
		print('Discord Ready', self.user)
		# await self.user.edit(username='Hermes')

	async def on_message(self, message):
		"""
		TODO only send for registered channel, before "registration" do not send anything
		TODO is the sent name the current set discord name? or is it the account name?
		"""
		author, channel, text = message.author.name, message.channel.name, message.content
		for connection in state.connections:
			await connection.websocket.send_json({
				'type': 'text',
				'author': author,
				'channel': channel,
				'text': text,
			})

	async def send_message(self, serverid, channelid, text):
		guild = discord.utils.get(state.discord.guilds, id=int(serverid))
		if guild is None:
			return
		channel = discord.utils.get(guild.channels, id=int(channelid))
		if type(channel) != discord.channel.TextChannel:
			return
		await channel.send(text)

async def task_discord(loop):
	client = MyClient(loop=loop)
	state.discord = client
	await client.login(DISCORD_TOKEN)
	await client.connect()

# Main

loop = asyncio.get_event_loop()
#loop.create_task(task_timer(loop))
loop.create_task(task_discord(loop))
# loop.create_task(task_web(loop))
loop.run_until_complete(task_web(loop))
# loop.run_forever()
