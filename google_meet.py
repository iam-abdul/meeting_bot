from playwright.sync_api import sync_playwright, Page, TimeoutError
import os
from typing import Optional
import logging
import time

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
            selectors = [
                f'div[role="button"][aria-label*="{device_type}"]',
                f'div[role="button"][data-is-muted][aria-label*="{device_type}"]',
                f'div[jsname][role="button"][aria-label*="{device_type}"]'
            ]
            
            for selector in selectors:
                logger.debug(f"Trying selector: {selector}")
                button = page.locator(selector).first
                if button.is_visible(timeout=5000):
                    state = button.get_attribute('data-is-muted', timeout=5000)
                    if state is None or state == 'false':
                        logger.info(f"Turning off {device_type}")
                        button.click()
                        time.sleep(1)  # Wait for state to update
                        logger.info(f"{device_type.capitalize()} turned off successfully")
                    else:
                        logger.info(f"{device_type.capitalize()} is already off")
                    return
            logger.warning(f"No matching {device_type} control found")
        except TimeoutError as e:
            logger.warning(f"Could not find {device_type} button: {e}")
        except Exception as e:
            logger.error(f"Error toggling {device_type}: {e}")

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

    def join_google_meet(self, meet_url: str) -> None:
        """Join a Google Meet call with video and microphone turned off."""
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
                
                if not self._wait_for_meeting_load(page):
                    logger.error("Failed to load meeting interface")
                    return
                
                logger.info("Configuring meeting settings...")
                self._toggle_device(page, "camera")
                self._toggle_device(page, "microphone")
                
                if self._join_meeting(page):
                    elapsed_time = time.time() - start_time
                    logger.info(f"Successfully joined the meeting (took {elapsed_time:.1f} seconds)")
                    logger.info("Waiting for 5 seconds to ensure connection...")
                    page.wait_for_timeout(5000)
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