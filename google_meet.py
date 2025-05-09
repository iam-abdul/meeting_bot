from playwright.sync_api import sync_playwright, Page, TimeoutError
import os
from typing import Optional
import logging
import time
import json
from datetime import datetime
import openai
from dotenv import load_dotenv
import requests

# Load environment variables
load_dotenv()

# Set up logging with timestamp
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

class GoogleMeetController:
    def __init__(self, user_data_dir: Optional[str] = None):
        self.user_data_dir = user_data_dir or os.path.join(os.getcwd(), 'browser_data')
        logger.info(f"Initializing GoogleMeetController with data directory: {self.user_data_dir}")
        # Create a directory for storing transcripts if it doesn't exist
        self.transcripts_dir = os.path.join(os.getcwd(), 'transcripts')
        os.makedirs(self.transcripts_dir, exist_ok=True)

    def setup_browser(self) -> None:
        """Launch a browser for first-time setup. User should manually sign in."""
        logger.info("Starting browser setup process")
        with sync_playwright() as p:
            try:
                logger.info("Launching browser for setup")
                context = p.chromium.launch_persistent_context(
                    user_data_dir=self.user_data_dir,
                    headless=False
                )
                page = context.new_page()
                logger.info("Navigating to Google sign-in page")
                page.goto('https://accounts.google.com')
                
                print("\n=== Google Sign-in Required ===")
                print("1. Please sign in to your Google account in the browser window")
                print("2. After signing in, you can close the browser window")
                print("3. The session will be saved for future use")
                print("4. You have 5 minutes to complete this process\n")
                
                try:
                    page.wait_for_event('close', timeout=300000)  # 5 minutes timeout
                    logger.info("Browser window closed, setup completed successfully")
                except TimeoutError:
                    logger.warning("Setup timed out after 5 minutes")
                except Exception as e:
                    logger.error(f"Setup error: {e}")
            except Exception as e:
                logger.error(f"Failed to launch browser for setup: {e}")
            finally:
                context.close()
                logger.info("Browser setup process completed")

    def _wait_for_meeting_load(self, page: Page) -> bool:
        """Wait for the meeting interface to load completely."""
        logger.info("Waiting for meeting interface to load...")
        try:
            # Wait for any of these elements that indicate the meeting UI is ready
            selectors = [
                'div[role="button"][aria-label*="camera"]',  # Camera button
                'div[role="button"][aria-label*="microphone"]',  # Mic button
                'button:has-text("Join now")',  # Join button
                'button:has-text("Ask to join")'  # Alternative join button
            ]
            
            # Use a shorter timeout for individual elements
            for selector in selectors:
                if page.locator(selector).first.is_visible(timeout=5000):
                    logger.info("Meeting interface detected")
                    # Give a short pause for all elements to be fully interactive
                    page.wait_for_timeout(2000)
                    return True
            
            logger.error("Could not detect meeting interface elements")
            return False
            
        except Exception as e:
            logger.error(f"Error waiting for meeting interface: {e}")
            return False

    def _toggle_device(self, page: Page, device_type: str) -> None:
        """Toggle camera or microphone if it's on."""
        logger.info(f"Checking {device_type} status...")
        try:
            # Wait for the pre-join screen to stabilize
            page.wait_for_timeout(2000)

            # Comprehensive selectors for device controls
            selectors = [
                # New Meet UI selectors
                f'button[data-is-muted][aria-label*="{device_type}"]',
                f'button[data-is-muted][aria-label*="{device_type.capitalize()}"]',
                # Classic Meet UI selectors
                f'div[role="button"][data-is-muted][aria-label*="{device_type}"]',
                f'div[role="button"][data-is-muted][aria-label*="{device_type.capitalize()}"]',
                # General selectors
                f'[role="button"][aria-label*="{device_type}"]',
                f'[role="button"][aria-label*="{device_type.capitalize()}"]',
                # Additional selectors for specific cases
                f'[data-tooltip*="{device_type}"][role="button"]',
                f'[data-tooltip*="{device_type.capitalize()}"][role="button"]',
                # Fallback to any element with matching aria-label
                f'[aria-label*="{device_type}"]',
                f'[aria-label*="{device_type.capitalize()}"]'
            ]

            # Try each selector
            for selector in selectors:
                logger.debug(f"Trying selector: {selector}")
                elements = page.locator(selector).all()
                for button in elements:
                    try:
                        if button.is_visible(timeout=1000):
                            # Check various attributes that might indicate device state
                            aria_label = button.get_attribute('aria-label', timeout=1000) or ''
                            is_muted = button.get_attribute('data-is-muted', timeout=1000)
                            tooltip = button.get_attribute('data-tooltip', timeout=1000) or ''
                            
                            # Log the found element details for debugging
                            logger.debug(f"Found {device_type} control:")
                            logger.debug(f"- aria-label: {aria_label}")
                            logger.debug(f"- data-is-muted: {is_muted}")
                            logger.debug(f"- tooltip: {tooltip}")
                            
                            # Check if device is already off
                            if (is_muted == 'true' or 
                                'off' in aria_label.lower() or 
                                'muted' in aria_label.lower() or
                                'off' in tooltip.lower() or
                                'muted' in tooltip.lower()):
                                logger.info(f"{device_type.capitalize()} is already off")
                                return

                            # If we get here, device is probably on, so turn it off
                            logger.info(f"Turning off {device_type}")
                            button.click()
                            # Wait for state change
                            page.wait_for_timeout(1000)
                            logger.info(f"{device_type.capitalize()} turned off")
                            return
                    except Exception as e:
                        logger.debug(f"Error checking element with selector {selector}: {e}")
                        continue

            logger.warning(f"No matching {device_type} control found after trying all selectors")
        except Exception as e:
            logger.error(f"Error handling {device_type}: {e}")

    def _join_meeting(self, page: Page) -> bool:
        """Click the join meeting button."""
        logger.info("Attempting to join the meeting...")
        try:
            selectors = [
                'button:has-text("Join now")',
                'button:has-text("Ask to join")',
                'div[role="button"]:has-text("Join now")',
                'div[role="button"]:has-text("Ask to join")'
            ]
            
            for selector in selectors:
                logger.debug(f"Looking for join button with selector: {selector}")
                button = page.locator(selector).first
                if button.is_visible(timeout=5000):
                    logger.info(f"Found join button: {selector}")
                    button.click()
                    logger.info("Join button clicked successfully")
                    return True
            
            logger.error("Could not find any join button")
            return False
            
        except Exception as e:
            logger.error(f"Error joining meeting: {e}")
            return False

    def _turn_on_captions(self, page: Page) -> bool:
        """Turn on meeting captions if they're not already enabled."""
        logger.info("Attempting to turn on captions...")
        try:
            # Wait for meeting UI to stabilize first
            logger.info("Waiting for meeting UI to stabilize before enabling captions...")
            page.wait_for_timeout(5000)
            
            # Simply press the 'c' key to toggle captions
            try:
                page.keyboard.press("c")
                logger.info("Pressed 'c' key to toggle captions")
                page.wait_for_timeout(2000)
                return True
            except Exception as key_error:
                logger.error(f"Error pressing 'c' key: {str(key_error)}")
                return False
            
        except Exception as e:
            logger.error(f"Error turning on captions: {str(e)}")
            return False

    def _monitor_participants(self, page: Page) -> None:
        """Monitor the number of participants and leave when everyone else has left."""
        logger.info("Starting to monitor participants...")
        try:
            # Give UI time to fully load after joining
            logger.info("Waiting for meeting UI to stabilize...")
            page.wait_for_timeout(5000)

            about_to_leave = False
            leave_countdown = 30  # 30 seconds countdown
            
            # Initialize transcript extraction variables
            transcript_data = []
            meeting_date = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
            filename = os.path.join(self.transcripts_dir, f"transcript_{meeting_date}.json")
            
            # Create a file for real-time transcript saving
            with open(filename, 'w') as f:
                f.write('{"transcript": []}')
            
            logger.info("Starting transcript extraction alongside participant monitoring...")
            
            # Ensure captions are turned on after starting transcript extraction
            try:
                # Wait a bit longer for the UI to fully stabilize after joining
                logger.info("Waiting for meeting UI to fully stabilize before enabling captions...")
                page.wait_for_timeout(3000)
                
                # First check if captions button is visible and what state it's in
                caption_button = page.locator('button[aria-label="Turn on captions"], button[jsname="r8qRAd"]').first
                if caption_button.is_visible(timeout=2000):
                    # If button is visible and not pressed, click it
                    try:
                        aria_pressed = caption_button.get_attribute("aria-pressed")
                        if aria_pressed == "false":
                            logger.info("Found captions button in unpressed state, clicking it...")
                            caption_button.click(timeout=3000)
                            logger.info("Clicked captions button directly")
                            page.wait_for_timeout(2000)
                    except Exception as button_error:
                        logger.debug(f"Error checking button state: {str(button_error)}")
                
                # Check if captions are already on by looking for caption elements
                caption_elements = page.locator('div.nMcdL, div.a4cQT, div.CNOXVe')
                if caption_elements.count() == 0:
                    logger.info("No caption elements found, pressing 'c' key to enable captions...")
                    page.keyboard.press("c")
                    logger.info("Pressed 'c' key to toggle captions after transcript extraction started")
                    page.wait_for_timeout(3000)
                    
                    # Check again for caption elements
                    caption_elements = page.locator('div.nMcdL, div.a4cQT, div.CNOXVe')
                    if caption_elements.count() == 0:
                        logger.info("Still no caption elements, trying 'Shift+c'...")
                        page.keyboard.press("Shift+c")
                        logger.info("Pressed 'Shift+c' key to toggle captions")
                        page.wait_for_timeout(3000)
                        
                        # If still no captions, try one more time with the 'c' key
                        caption_elements = page.locator('div.nMcdL, div.a4cQT, div.CNOXVe')
                        if caption_elements.count() == 0:
                            logger.info("Final attempt to enable captions with 'c' key...")
                            page.keyboard.press("c")
                            logger.info("Pressed 'c' key again for final attempt")
                            page.wait_for_timeout(3000)
                else:
                    logger.info("Caption elements already detected, captions are enabled")
            except Exception as caption_error:
                logger.error(f"Error ensuring captions are on: {str(caption_error)}")

            while True:
                try:
                    # Look for the specific participant count div
                    count_div = page.locator('div.uGOf1d').first
                    if count_div.is_visible(timeout=1000):
                        count_text = count_div.text_content()
                        try:
                            count = int(count_text)
                            logger.info(f"Current participant count: {count}")
                            
                            if count == 1:
                                if not about_to_leave:
                                    about_to_leave = True
                                    logger.info(f"Only 1 participant detected. Will leave in {leave_countdown} seconds...")
                                    page.wait_for_timeout(leave_countdown * 1000)  # Convert to milliseconds
                                    logger.info("Leaving meeting as countdown finished...")
                                    self._leave_meeting(page)
                                    break
                            else:
                                about_to_leave = False
                        except ValueError:
                            logger.debug(f"Could not convert count text to integer: {count_text}")
                except Exception as e:
                    logger.debug(f"Error checking participant count: {e}")
                
                # Extract transcript data during each monitoring cycle
                try:
                    # Look for caption container
                    caption_elements = page.locator('div.nMcdL')
                    count = caption_elements.count()
                    
                    if count > 0:
                        for i in range(count):
                            try:
                                caption_element = caption_elements.nth(i)
                                
                                # Extract speaker name
                                speaker_element = caption_element.locator('span.NWpY1d').first
                                speaker_name = speaker_element.text_content() if speaker_element.is_visible(timeout=500) else "Unknown"
                                
                                # Extract caption text
                                text_element = caption_element.locator('div.bh44bd').first
                                caption_text = text_element.text_content() if text_element.is_visible(timeout=500) else ""
                                
                                if caption_text:
                                    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                                    entry = {
                                        "timestamp": timestamp,
                                        "speaker": speaker_name,
                                        "text": caption_text
                                    }
                                    
                                    # Check if this is a new entry to avoid duplicates
                                    if not any(existing["text"] == caption_text and existing["speaker"] == speaker_name 
                                              for existing in transcript_data):
                                        transcript_data.append(entry)
                                        logger.info(f"New caption from {speaker_name}: {caption_text[:30]}...")
                                        
                                        # Save transcript incrementally
                                        with open(filename, 'r') as f:
                                            data = json.load(f)
                                        
                                        data["transcript"].append(entry)
                                        
                                        with open(filename, 'w') as f:
                                            json.dump(data, f, indent=2)
                            except Exception as e:
                                logger.debug(f"Error processing caption element {i}: {e}")
                except Exception as e:
                    logger.debug(f"Error during caption extraction cycle: {e}")
                
                # Wait before next check
                page.wait_for_timeout(5000)

        except Exception as e:
            logger.error(f"Error in participant monitoring: {e}")
            
            # Try to save whatever transcript we've collected so far
            if 'transcript_data' in locals() and transcript_data and 'filename' in locals():
                try:
                    with open(filename, 'w') as f:
                        json.dump({"transcript": transcript_data}, f, indent=2)
                    logger.info(f"Saved partial transcript to {filename}")
                except Exception as save_error:
                    logger.error(f"Failed to save partial transcript: {save_error}")
                    
            self._leave_meeting(page)
        
        # After leaving the meeting, summarize the transcript
        if 'filename' in locals() and os.path.exists(filename):
            logger.info("Meeting ended. Generating transcript summary...")
            summary = self._summarize_transcript(filename)
            logger.info(f"Transcript summary: {summary[:100]}...")  # Log the first 100 chars of summary

    def _leave_meeting(self, page: Page) -> None:
        """Attempt to leave the meeting gracefully."""
        leave_selectors = [
            'button[aria-label*="leave"]',
            'button[aria-label*="Leave"]',
            '[role="button"][aria-label*="leave"]',
            '[role="button"][aria-label*="Leave"]',
            'button[aria-label="Leave call"]',
            '[data-mdc-dialog-action="leave"]'
        ]
        for selector in leave_selectors:
            try:
                button = page.locator(selector).first
                if button.is_visible(timeout=1000):
                    button.click()
                    logger.info("Successfully left the meeting")
                    return
            except:
                continue
        
        logger.warning("Could not find leave button, closing browser")

    def _summarize_transcript(self, transcript_file: str) -> str:
        """
        Summarize the meeting transcript using OpenAI.
        
        Args:
            transcript_file: Path to the JSON file containing the transcript
            
        Returns:
            str: The summary of the meeting
        """
        logger.info(f"Summarizing transcript from {transcript_file}")
        try:
            # Check if OpenAI API key is available
            api_key = os.getenv("OPENAI_API_KEY")
            if not api_key:
                logger.error("OpenAI API key not found in environment variables")
                return "Error: OpenAI API key not found in environment variables"
            
            # Set the API key
            openai.api_key = api_key
            
            # Load the transcript
            with open(transcript_file, 'r') as f:
                data = json.load(f)
            
            # Log the transcript data structure for debugging
            logger.info(f"Transcript data structure: {json.dumps(data, indent=2)[:500]}...")
            
            if not data or "transcript" not in data or not data["transcript"]:
                logger.warning("No transcript data found to summarize")
                error_msg = "No transcript data available for summarization"
                
                # Save the error message to the summary file
                summary_file = transcript_file.replace(".json", "_summary.txt")
                with open(summary_file, 'w') as f:
                    f.write(error_msg)
                
                logger.info(f"Empty summary notification saved to {summary_file}")
                return error_msg
            
            # Log transcript length for debugging
            logger.info(f"Found {len(data['transcript'])} transcript entries to summarize")
            
            # Preprocess transcript to remove duplicates and partial entries
            processed_entries = []
            speakers_text = {}  # Dictionary to track the latest text from each speaker
            
            # Sort entries by timestamp
            sorted_entries = sorted(data['transcript'], key=lambda x: x['timestamp'])
            
            for entry in sorted_entries:
                speaker = entry['speaker']
                text = entry['text']
                
                # Check if this is a new speaker or a completely different message
                if speaker not in speakers_text or not text.startswith(speakers_text[speaker][:min(len(speakers_text[speaker]), 20)]):
                    # This is a new message
                    processed_entries.append(entry)
                    speakers_text[speaker] = text
                else:
                    # This might be an updated version of the previous message
                    if len(text) > len(speakers_text[speaker]):
                        # Replace the previous entry with this more complete one
                        for i, prev_entry in enumerate(processed_entries):
                            if prev_entry['speaker'] == speaker and prev_entry['text'].startswith(text[:min(len(prev_entry['text']), 20)]):
                                processed_entries[i] = entry
                                break
                        else:
                            # If no match found, add as new entry
                            processed_entries.append(entry)
                        
                        speakers_text[speaker] = text
            
            logger.info(f"Processed transcript from {len(data['transcript'])} to {len(processed_entries)} entries after removing duplicates")
            
            # Format the processed transcript for the API
            formatted_transcript = ""
            for entry in processed_entries:
                formatted_transcript += f"{entry['speaker']}: {entry['text']}\n"
            
            # Log a sample of the formatted transcript
            logger.info(f"Formatted transcript sample: {formatted_transcript[:500]}...")
            
            # Create the prompt for summarization
            prompt = f"Please provide a concise summary of the following meeting transcript, highlighting key points, decisions, and action items:\n\n{formatted_transcript}"
            
            # Call the OpenAI API
            logger.info("Calling OpenAI API to generate summary")
            response = openai.chat.completions.create(
                model="o4-mini-2025-04-16",  # Can be configured based on needs
                messages=[
                    {"role": "system", "content": "You are a helpful assistant that summarizes meeting transcripts."},
                    {"role": "user", "content": prompt}
                ],
                max_completion_tokens=1500
            )
            
            # Log the full API response for debugging
            logger.info(f"OpenAI API response: {response}")
            
            # Extract and return the summary
            summary = response.choices[0].message.content
            logger.info(f"Generated summary: {summary}")
            
            # Save the summary alongside the transcript
            summary_file = transcript_file.replace(".json", "_summary.txt")
            with open(summary_file, 'w') as f:
                f.write(summary)
            
            logger.info(f"Summary saved to {summary_file}")
            
            # Post the summary to the webhook URL if configured
            webhook_url = os.getenv("WEBHOOK_URL")
            if webhook_url:
                try:
                    logger.info(f"Posting summary to webhook: {webhook_url}")
                    
                    # Prepare payload with meeting details and summary
                    payload = {
                        "meeting_date": datetime.now().strftime("%Y-%m-%d_%H-%M-%S"),
                        "transcript_file": os.path.basename(transcript_file),
                        "summary": summary,
                        "timestamp": datetime.now().isoformat()
                    }
                    
                    # Send POST request to webhook
                    response = requests.post(
                        webhook_url,
                        json=payload,
                        headers={"Content-Type": "application/json"}
                    )
                    
                    if response.status_code >= 200 and response.status_code < 300:
                        logger.info(f"Successfully posted summary to webhook. Response: {response.status_code}")
                    else:
                        logger.error(f"Failed to post summary to webhook. Status code: {response.status_code}, Response: {response.text}")
                        
                except Exception as webhook_error:
                    logger.error(f"Error posting summary to webhook: {webhook_error}")
            else:
                logger.warning("WEBHOOK_URL not configured in .env file. Summary not posted.")
            
            return summary
            
        except Exception as e:
            logger.error(f"Error summarizing transcript: {e}")
            error_msg = f"Error summarizing transcript: {str(e)}"
            
            # Save the error message to the summary file
            try:
                summary_file = transcript_file.replace(".json", "_summary.txt")
                with open(summary_file, 'w') as f:
                    f.write(error_msg)
                logger.info(f"Error message saved to {summary_file}")
            except Exception as write_error:
                logger.error(f"Failed to write error message to summary file: {write_error}")
            
            # Try to post error to webhook if configured
            webhook_url = os.getenv("WEBHOOK_URL")
            if webhook_url:
                try:
                    logger.info(f"Posting error to webhook: {webhook_url}")
                    
                    # Prepare payload with error details
                    payload = {
                        "meeting_date": datetime.now().strftime("%Y-%m-%d_%H-%M-%S"),
                        "transcript_file": os.path.basename(transcript_file),
                        "error": error_msg,
                        "timestamp": datetime.now().isoformat()
                    }
                    
                    # Send POST request to webhook
                    response = requests.post(
                        webhook_url,
                        json=payload,
                        headers={"Content-Type": "application/json"}
                    )
                    
                    logger.info(f"Error posted to webhook. Response: {response.status_code}")
                except Exception as webhook_error:
                    logger.error(f"Error posting error to webhook: {webhook_error}")
                
            return error_msg

    def _extract_and_save_transcript(self, page: Page) -> None:
        """
        This method is deprecated. Transcript extraction is now handled in _monitor_participants.
        This stub remains for backward compatibility.
        """
        logger.warning("The _extract_and_save_transcript method is deprecated. Transcripts are now handled in _monitor_participants.")
        pass

    def join_google_meet(self, meet_url: str) -> None:
        """Join a Google Meet call."""
        logger.info(f"Starting to join meeting: {meet_url}")
        start_time = time.time()
        
        with sync_playwright() as p:
            try:
                logger.info("Launching browser...")
                context = p.chromium.launch_persistent_context(
                    user_data_dir=self.user_data_dir,
                    headless=False
                )
                
                page = context.new_page()
                logger.info(f"Navigating to meeting URL: {meet_url}")
                page.goto(meet_url)
                
                if self._wait_for_meeting_load(page):
                    logger.info("Configuring meeting settings...")
                    self._toggle_device(page, "camera")
                    self._toggle_device(page, "microphone")
                    
                    if self._join_meeting(page):
                        elapsed_time = time.time() - start_time
                        logger.info(f"Successfully joined the meeting (took {elapsed_time:.1f} seconds)")
                        
                        # Start monitoring participants and extracting transcript
                        # Captions will be enabled during the monitoring phase
                        self._monitor_participants(page)
                    else:
                        logger.error("Failed to join the meeting")
                
            except Exception as e:
                logger.error(f"Unexpected error while joining meeting: {e}")
            finally:
                logger.info("Closing browser")
                context.close()
                total_time = time.time() - start_time
                logger.info(f"Meeting join process completed in {total_time:.1f} seconds")

if __name__ == "__main__":
    # If run directly, launch the setup browser
    controller = GoogleMeetController()
    controller.setup_browser()