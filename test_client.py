import socketio
import asyncio

sio = socketio.AsyncClient()

@sio.event
async def connect():
    print("Connected to server from python client!")
    await sio.emit('join_interview', {'session_slug': 'test-session-123'})
    print("Sent join_interview")

@sio.event
async def disconnect():
    print("Disconnected from server")

@sio.event
async def system_message(data):
    print(f"System message received: {data}")
    await sio.emit('user_answer', {'session_slug': 'test-session-123', 'text': 'Hello from script'})

@sio.event
async def transcript_update(data):
    print(f"Transcript update: {data}")

@sio.event
async def status_update(data):
    print(f"Status update: {data}")

async def main():
    try:
        await sio.connect('http://localhost:8000', transports=['polling', 'websocket'])
        await sio.wait()
    except Exception as e:
        print(f"Error connecting: {e}")

if __name__ == '__main__':
    asyncio.run(main())
