
import asyncio
import collections
import discord
import os
import starlette
import starlette.applications
import starlette.status
import starlette.config
import time
import uvicorn
import types
import base64

"""
TODO put routes into namespace/class
TODO decouple State/Discord/Starlette
TODO replace starlette with FastAPI?
TODO do not start the service when the important env variables are not set correctly
TODO add a register message? instead of sending author, channel, ... everytime?
TODO Server ID is more unique id than Server name, and also does not change. For a channel the ID may be a better idea, but its somewhat more complicated to get the channel id, and if channels are deleted/recreated the IDs also change. See Your User Settings -> Advanced -> Develop Mode ... New Context Menu appears copy ID
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
	TODO use aio loop
	TODO change this into a Discord fake emulation to test the service without Discord
	"""
	while True:
		print('Timer', 'connected#', len(state.connections))
		for (i, connection) in enumerate(state.connections):
			text = 'Hello From Server. You ID Is ' + str(i) + '. Time Is ' + str(time.time())
			await connection.websocket.send_json({'type': 'text', 'text': text})
		await asyncio.sleep(5.0)

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
	websocket = connection.websocket
	if message.type == 'ping':
		await websocket.send_json({'type': 'pong'})
	elif message.type == 'text':
		connection.channelid, connection.author = message.channelid, message.author
		text = '**' + message.author + '**: ' + message.text
		if state.discord is not None:
			guild = discord.utils.get(state.discord.guilds, id=int(message.serverid))
			if guild is None:
				return
			channel = discord.utils.get(guild.channels, id=int(message.channelid))
			if type(channel) != discord.channel.TextChannel:
				return
			await channel.send(text)

async def websocket(websocket):
	await websocket.accept()
	connection = dict2obj({
		'websocket': websocket,
		'author': '',
		'channel': None,
	})
	state.connections.append(connection)
	state.count_connections[websocket.client.host] += 1
	# TODO notify discord that user entered, use origin header to show from where the connection was opened (maybe use https://docs.python.org/3/library/urllib.parse.html)
	if state.discord is not None:
		pass
	try:
		while True:
			message = dict2obj(await websocket.receive_json())
			#print('message', message)
			await handle_message(connection, message)
	except starlette.websockets.WebSocketDisconnect:
		pass
	except Exception as e:
		print(e)
		# TODO add to statistics?
	if state.discord is not None:
		pass
	# TODO notify discord that user left
	state.connections.remove(connection)

async def task_web(loop):
	routes = [
		starlette.routing.Route('/', root),
		starlette.routing.Route('/demo', demo),
		starlette.routing.Route('/status', status),
		starlette.routing.WebSocketRoute('/ws', websocket),
	]
	app = starlette.applications.Starlette(debug=True, routes=routes)
	config = uvicorn.Config(app=app, loop=loop, port=8000, host='0.0.0.0')
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
		await message.add_reaction('✅')
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

async def task_discord(loop):
	"""
	TODO use aio loop
	"""
	assert len(DISCORD_TOKEN) > 0
	client = MyClient()
	state.discord = client
	await client.login(DISCORD_TOKEN)
	await client.connect()

# Main

loop = asyncio.get_event_loop()
#loop.create_task(task_timer(loop))
loop.create_task(task_discord(loop))
# loop.create_task(task_web())
loop.run_until_complete(task_web(loop))
# loop.run_forever()
