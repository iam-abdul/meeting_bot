from playwright.sync_api import sync_playwright

def join_google_meet(meet_url: str):
    """
    Join a Google Meet call with video and microphone turned off
    
    Args:
        meet_url (str): The Google Meet URL to join
    """
    with sync_playwright() as p:
        # Launch the browser
        browser = p.chromium.launch(headless=False)
        context = browser.new_context()
        
        # Create a new page
        page = context.new_page()
        
        # Navigate to Google Meet
        page.goto(meet_url)
        
        # Wait for the pre-meeting screen to load
        page.wait_for_selector('div[role="button"]')
        
        # Turn off camera (if it's on)
        camera_button = page.locator('div[role="button"][aria-label*="camera"]').first
        if 'is-on' in camera_button.get_attribute('class', ''):
            camera_button.click()
            
        # Turn off microphone (if it's on)
        mic_button = page.locator('div[role="button"][aria-label*="microphone"]').first
        if 'is-on' in mic_button.get_attribute('class', ''):
            mic_button.click()
        
        # Click "Join now" button
        join_button = page.get_by_role("button", name="Join now")
        join_button.click()
        
        # Wait in the meeting
        page.wait_for_timeout(5000)  # Wait for 5 seconds, adjust as needed
        
        # Close the browser
        browser.close()