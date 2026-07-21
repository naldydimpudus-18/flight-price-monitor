from playwright.sync_api import sync_playwright

URL = "https://www.traveloka.com/en-id/flight/fullsearch?ap=DPS.GTO&dt=21-12-2026.NA&ps=1.0.0&sc=ECONOMY"

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)

    page = browser.new_page()

    page.goto(
        URL,
        wait_until="networkidle",
        timeout=120000
    )

    print("TITLE:")
    print(page.title())

    page.screenshot(
        path="traveloka-gto.png",
        full_page=True
    )

    browser.close()
