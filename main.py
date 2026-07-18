from playwright.sync_api import sync_playwright

URL = "https://www.google.com/travel/flights/search?tfs=CBwQAhokEgoyMDI2LTEyLTIxag0IAhIJL20vMDJuYmgxcgcIARIDR1RPQAFIAXABggELCP___________wGYAQI"

with sync_playwright() as p:
    browser = p.chromium.launch(
        headless=True,
        args=["--no-sandbox"]
    )

    page = browser.new_page(
        viewport={"width": 1600, "height": 1200}
    )

    page.goto(URL, wait_until="networkidle", timeout=120000)

    page.screenshot(
        path="flight.png",
        full_page=True
    )

    print("=" * 50)
    print(page.title())
    print(page.url)
    print("=" * 50)

    browser.close()
