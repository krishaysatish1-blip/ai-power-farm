import asyncio
from playwright.async_api import async_playwright

async def add_etc_network():
    async with async_playwright() as p:
        # Launch Chrome with existing profile (has MetaMask)
        user_data_dir = r"C:\Users\krish-v\AppData\Local\Google\Chrome\User Data"
        
        context = await p.chromium.launch_persistent_context(
            user_data_dir,
            channel="chrome",
            headless=False,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-first-run",
                "--no-default-browser-check"
            ]
        )
        
        page = context.pages[0] if context.pages else await context.new_page()
        
        # Go to chainlist to add ETC network
        print("Opening chainlist.org...")
        await page.goto("https://chainlist.org/chain/61", wait_until="networkidle", timeout=30000)
        await asyncio.sleep(3)
        
        # Click "Add to MetaMask" button
        print("Looking for Add to MetaMask button...")
        add_btn = page.locator("button:has-text('Add to MetaMask')").first
        if await add_btn.is_visible():
            print("Clicking Add to MetaMask...")
            await add_btn.click()
            await asyncio.sleep(3)
            
            # Switch to MetaMask popup window
            print("Waiting for MetaMask popup...")
            for _ in range(10):
                await asyncio.sleep(1)
                pages = context.pages
                for p_page in pages:
                    if "chrome-extension://" in p_page.url and "nkbihfbeogaeaoehlefnkodbefgpgknn" in p_page.url:
                        print("Found MetaMask popup!")
                        await asyncio.sleep(2)
                        
                        # Click Approve
                        try:
                            approve_btn = p_page.locator("button:has-text('Approve')")
                            if await approve_btn.is_visible(timeout=5000):
                                print("Clicking Approve...")
                                await approve_btn.click()
                                await asyncio.sleep(2)
                                print("ETC network added!")
                                
                                # Click Switch if available
                                try:
                                    switch_btn = p_page.locator("button:has-text('Switch')")
                                    if await switch_btn.is_visible(timeout=3000):
                                        await switch_btn.click()
                                        print("Switched to ETC network!")
                                except:
                                    pass
                        except Exception as e:
                            print(f"Approve error: {e}")
                        break
        else:
            print("Add to MetaMask button not found. Trying manual approach...")
        
        await asyncio.sleep(3)
        print("Done! Closing browser...")
        await context.close()

asyncio.run(add_etc_network())
