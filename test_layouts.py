import socketio
import time

sio = socketio.Client()

@sio.on('connect', namespace='/config')
def on_connect():
    print("Connected to /config")
    sio.emit('get_layouts', namespace='/config')

@sio.on('layouts_list', namespace='/config')
def on_layouts_list(data):
    print(f"Received layouts list: {data}")
    sio.disconnect()

sio.connect('http://localhost:5000', namespaces=['/config'])
sio.wait()
