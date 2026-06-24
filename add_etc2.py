import asyncio
from playwright.async_api import async_playwright

async def add_etc():
    async with async_playwright() as p:
        user_data_dir = r"C:\Users\krish-v\AppData\Local\Google\Chrome\User Data"
        
        context = await p.chromium.launch_persistent_context(
            user_data_dir,
            channel="chrome",
            headless=False,
            args=["--disable-blink-features=AutomationControlled","--no-first-run","--no-default-browser-check"]
        )
        
        page = context.pages[0] if context.pages else await context.new_page()
        
        # Go to MetaMask settings to add network
        print("Opening MetaMask...")
        await page.goto("chrome-extension://nkbihfbeogaeaoehlefnkodbefgpgknn/home.html#settings/networks/add-network", wait_until="networkidle", timeout=30000)
        await asyncio.sleep(3)
        
        print("Page URL:", page.url)
        print("Page title:", await page.title())
        
        # Take screenshot to see what's on screen
        await page.screenshot(path=r"C:\Users\krish-v\Pictures\ai\metamask_screenshot.png")
        print("Screenshot saved")
        
        await asyncio.sleep(2)
        await context.close()

asyncio.run(add_etc())
