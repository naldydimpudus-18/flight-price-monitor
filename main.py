from playwright.sync_api import sync_playwright

URL = "https://www.google.com/travel/flights/search?tfs=CBwQAhokEgoyMDI2LTEyLTIxag0IAhIJL20vMDJuYmgxcgcIARIDR1RPQAFIAXABggELCP___________wGYAQI"

with sync_playwright() as p:
    browser = p.chromium.launch(
        headless=True
    )

    page = browser.new_page()

    page.goto(URL, wait_until="networkidle", timeout=120000)

    print("TITLE:")
    print(page.title())

    page.screenshot(path="google-flights.png", full_page=True)

    print("SCREENSHOT SAVED")

    browser.close()
