import os
import asyncio
from playwright.async_api import async_playwright

EXAROTON_EMAIL = os.getenv("EXAROTON_EMAIL")
EXAROTON_PASSWORD = os.getenv("EXAROTON_PASSWORD")
EXAROTON_SERVER_ID = os.getenv("EXAROTON_SERVER_ID")

async def get_live_status_playwright():
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context()
            page = await context.new_page()

            # Login page
            await page.goto("https://exaroton.com/login", timeout=15000)
            await page.fill('input[name="email"]', EXAROTON_EMAIL)
            await page.fill('input[name="password"]', EXAROTON_PASSWORD)
            await page.click('button[type="submit"]')

            # Wait for login to complete
            await page.wait_for_url("https://exaroton.com/dashboard", timeout=10000)

            # Navigate to server page
            await page.goto(f"https://exaroton.com/server/{EXAROTON_SERVER_ID}", timeout=15000)
            await page.wait_for_selector(".statusBadge", timeout=5000)

            motd = await page.locator(".motd").inner_text()
            status = await page.locator(".statusBadge").inner_text()
            players = await page.locator(".players .name").all_inner_texts()

            await browser.close()
            return {"motd": motd, "status": status, "players": players}

    except Exception as e:
        return {"error": str(e)}
