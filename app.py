from flask import Flask, request, jsonify
from google_meet import GoogleMeetController
import threading
import os
import logging

# Set up logging with timestamp
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

app = Flask(__name__)
meet_controller = GoogleMeetController()

@app.route('/api/join/google-meet', methods=['POST'])
def handle_join_google_meet():
    """Handle requests to join a Google Meet."""
    try:
        data = request.get_json()
        meeting_url = data.get('meeting_url')
        
        if not meeting_url:
            logger.error("Missing meeting_url in request")
            return jsonify({'error': 'meeting_url is required'}), 400
        
        logger.info(f"Received request to join meeting: {meeting_url}")
        
        # Start the bot in a separate thread to not block the API response
        thread = threading.Thread(
            target=meet_controller.join_google_meet,
            args=(meeting_url,)
        )
        thread.daemon = True  # Make thread daemon so it doesn't block app shutdown
        thread.start()
        
        logger.info(f"Started join process for meeting: {meeting_url}")
        return jsonify({
            'status': 'success',
            'message': 'Bot is joining the meeting',
            'meeting_url': meeting_url
        })
    except Exception as e:
        logger.error(f"Error processing join request: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/setup', methods=['POST'])
def handle_setup():
    """Setup endpoint to initialize browser and Google sign-in."""
    try:
        logger.info("Received setup request")
        thread = threading.Thread(target=meet_controller.setup_browser)
        thread.daemon = True
        thread.start()
        
        logger.info("Started browser setup process")
        return jsonify({
            'status': 'success',
            'message': 'Browser setup initiated. Please check the console for sign-in instructions.'
        })
    except Exception as e:
        logger.error(f"Error during setup: {e}")
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    logger.info("Starting Meeting Bot server on port 4500")
    app.run(debug=True, port=4500)