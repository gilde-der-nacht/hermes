import discord
import os
from dotenv import load_dotenv

load_dotenv()


class MyClient(discord.Client):
    async def on_ready(self):
        print(f'Logged on as {self.user}!')

    async def on_message(self, message):
        if (message.author == self.user):
            return
        await message.add_reaction('✅')
        await message.channel.send(f'Message received: "{message.content}"')


client = MyClient()
client.run(os.getenv('TOKEN'))
