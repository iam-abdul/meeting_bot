from flask import Flask, request, jsonify
from google_meet import join_google_meet
import threading
import os

app = Flask(__name__)

@app.route('/api/join/google-meet', methods=['POST'])
def handle_join_google_meet():
    data = request.get_json()
    meeting_url = data.get('meeting_url')
    
    if not meeting_url:
        return jsonify({'error': 'meeting_url is required'}), 400
    
    # Start the bot in a separate thread to not block the API response
    thread = threading.Thread(target=join_google_meet, args=(meeting_url,))
    thread.start()
    
    return jsonify({
        'status': 'success',
        'message': 'Bot is joining the meeting',
        'meeting_url': meeting_url
    })

if __name__ == '__main__':
    app.run(debug=True, port=4500)