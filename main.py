from playwright.sync_api import sync_playwright
import re

URL = "https://www.google.com/travel/flights/search?tfs=CBwQAhokEgoyMDI2LTEyLTIxag0IAhIJL20vMDJuYmgxcgcIARIDR1RPQAFIAXABggELCP___________wGYAQI"

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)

    page = browser.new_page()

    page.goto(URL, wait_until="networkidle", timeout=120000)

    text = page.locator("body").inner_text()

    match = re.search(r"\$(\d+)", text)

    if match:
        print(f"PRICE FOUND: ${match.group(1)}")
    else:
        print("PRICE NOT FOUND")

    page.screenshot(path="google-flights.png", full_page=True)

    browser.close()
