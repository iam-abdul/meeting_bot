from playwright.sync_api import sync_playwright
import os

def setup_browser(user_data_dir: str = None):
    """
    Launch a browser for first-time setup. User should manually sign in.
    The browser state will be saved for future use.
    """
    if user_data_dir is None:
        user_data_dir = os.path.join(os.getcwd(), 'browser_data')
    
    with sync_playwright() as p:
        # Launch browser with persistent context
        context = p.chromium.launch_persistent_context(
            user_data_dir=user_data_dir,
            headless=False
        )
        page = context.new_page()
        
        # Go to Google sign-in page
        page.goto('https://accounts.google.com')
        
        print("\nPlease sign in to your Google account in the browser window.")
        print("After signing in, you can close the browser window.")
        print("The session will be saved for future use.\n")
        
        # Wait for manual interaction and browser close
        try:
            page.wait_for_event('close', timeout=300000)  # 5 minutes timeout
        except:
            pass
        finally:
            context.close()

def join_google_meet(meet_url: str, user_data_dir: str = None):
    """
    Join a Google Meet call with video and microphone turned off
    
    Args:
        meet_url (str): The Google Meet URL to join
        user_data_dir (str): Directory to store browser state, defaults to './browser_data'
    """
    if user_data_dir is None:
        user_data_dir = os.path.join(os.getcwd(), 'browser_data')
    
    with sync_playwright() as p:
        # Launch browser with persistent context
        context = p.chromium.launch_persistent_context(
            user_data_dir=user_data_dir,
            headless=False
        )
        
        # Create a new page
        page = context.new_page()
        
        # Navigate to Google Meet
        page.goto(meet_url)
        
        # Wait for the pre-meeting screen to load
        page.wait_for_selector('div[role="button"]', timeout=30000)
        
        # Turn off camera (if it's on)
        camera_button = page.locator('div[role="button"][aria-label*="camera"]').first
        if camera_button and 'is-on' in camera_button.get_attribute('class', ''):
            camera_button.click()
            
        # Turn off microphone (if it's on)
        mic_button = page.locator('div[role="button"][aria-label*="microphone"]').first
        if mic_button and 'is-on' in mic_button.get_attribute('class', ''):
            mic_button.click()
        
        # Click "Join now" button
        join_button = page.get_by_role("button", name="Join now")
        join_button.click()
        
        # Wait in the meeting
        page.wait_for_timeout(5000)  # Wait for 5 seconds, adjust as needed
        
        # Close the browser
        context.close()

if __name__ == "__main__":
    # If run directly, launch the setup browser
    setup_browser()