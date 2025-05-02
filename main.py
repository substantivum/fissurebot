from typing import Final, Protocol
import os
from dotenv import load_dotenv
from discord import Intents, Client, Message
from responses import get_response

#load token
load_dotenv()
TOKEN: Final[str] = os.getenv("DISCORD_TOKEN")
print(TOKEN)

#bot setup
intents: Intents = Intents.default()
intents.message_content = True #NOQA
client : Client = Client(intents=intents)

async def send_message(message: Message, user_message: str) -> None:
    if not user_message:
        print("Message was empty, intents were not enabled")
        return

    is_private = user_message[0] == '?'

    if is_private:
        user_message = user_message[1:]

    try:
        response: str = get_response(user_message)
        await message.author.send(response) if is_private else await message.channel.send(response)

    except Exception as e:
        print(e)

#handle the startup
@client.event
async def on_ready() -> None:
    print(f'{client.user} has connected to Discord!')

#handle incoming messages
@client.event
async def on_message(message: Message) -> None:
    if message.author == client.user:
        return

    username: str = str(message.author)
    user_message: str = message.content
    channel: str = str(message.channel)

    print(f'[{channel}] {username} : {user_message}')
    await send_message(message, user_message)

    if user_message.startswith("/say "):
        to_say = user_message[5:].strip()
        if to_say:
            await message.channel.send(to_say)
        else:
            await message.channel.send("You didn't tell me what to say!")
        return

    await send_message(message, user_message)

def main() -> None:
    client.run(token=TOKEN)

if __name__ == '__main__':
    main()