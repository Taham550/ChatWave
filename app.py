from flask import Flask, render_template, request
from flask_socketio import SocketIO, emit, join_room, leave_room
import uuid
from datetime import datetime
import json
from flask_sqlalchemy import SQLAlchemy
app = Flask(__name__)
app.config['SECRET_KEY'] = 'taham'
socketio = SocketIO(app, cors_allowed_origins="*")
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///chat.db'
db = SQLAlchemy(app)

class Message(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), nullable=False)
    message = db.Column(db.Text, nullable=False)
    room = db.Column(db.String(80), nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

# Store active users and rooms
active_users = {}
chat_rooms = {
    'general': {
        'name': 'general',
        'users': [],
        'messages': []
    }
}

@app.route('/')
def index():
    return render_template('index.html')

@socketio.on('connect')
def on_connect():
    print(f'User connected: {request.sid}')

@socketio.on('disconnect')
def on_disconnect():
    print(f'User disconnected: {request.sid}')
    # Remove user from active users and rooms
    if request.sid in active_users:
        user_data = active_users[request.sid]
        room = user_data.get('room')
        if room and room in chat_rooms:
            if user_data in chat_rooms[room]['users']:
                chat_rooms[room]['users'].remove(user_data)
            # Notify room about user leaving
            emit('user_left', {
                'username': user_data['username'],
                'users_count': len(chat_rooms[room]['users'])
            }, room=room)
        del active_users[request.sid]

@socketio.on('join_chat')
def on_join_chat(data):
    username = data['username']
    room = data.get('room', 'general')
    
    # Create user data
    user_data = {
        'id': request.sid,
        'username': username,
        'room': room,
        'joined_at': datetime.now().isoformat()
    }
    
    # Store user
    active_users[request.sid] = user_data
    
    # Join room
    join_room(room)
    
    # Add user to room
    if room not in chat_rooms:
        chat_rooms[room] = {
            'name': room.title(),
            'users': [],
            'messages': []
        }
    
    chat_rooms[room]['users'].append(user_data)
    
    # Send room info to user
    emit('joined_room', {
        'room': room,
        'users': chat_rooms[room]['users'],
        'messages': chat_rooms[room]['messages'][-50:]  # Last 50 messages
    })
    
    # Notify room about new user
    emit('user_joined', {
        'username': username,
        'users_count': len(chat_rooms[room]['users'])
    }, room=room, include_self=False)

@socketio.on('send_message')
def on_send_message(data):
    if request.sid not in active_users:
        return
    
    user_data = active_users[request.sid]
    room = user_data['room']
    
    message_data = {
        'id': str(uuid.uuid4()),
        'username': user_data['username'],
        'message': data['message'],
        'timestamp': datetime.now().isoformat(),
        'user_id': request.sid
    }
    
    # Store message
    if room in chat_rooms:
        chat_rooms[room]['messages'].append(message_data)
        # Keep only last 100 messages
        if len(chat_rooms[room]['messages']) > 100:
            chat_rooms[room]['messages'] = chat_rooms[room]['messages'][-100:]
    
    # Broadcast message to room
    emit('new_message', message_data, room=room)

@socketio.on('typing')
def on_typing(data):
    if request.sid not in active_users:
        return
    
    user_data = active_users[request.sid]
    room = user_data['room']
    
    emit('user_typing', {
        'username': user_data['username'],
        'is_typing': data['is_typing']
    }, room=room, include_self=False)

@socketio.on('get_rooms')
def on_get_rooms():
    rooms_info = []
    for room_id, room_data in chat_rooms.items():
        rooms_info.append({
            'id': room_id,
            'name': room_data['name'],
            'users_count': len(room_data['users'])
        })
    emit('rooms_list', rooms_info)

if __name__ == '__main__':
    socketio.run(app, debug=True, host='0.0.0.0', port=5000)