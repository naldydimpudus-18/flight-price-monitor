from playwright.sync_api import sync_playwright

with sync_playwright() as p:

    browser = p.chromium.launch(
        headless=True,
        args=[
            "--disable-blink-features=AutomationControlled",
            "--disable-dev-shm-usage",
            "--no-sandbox",
            "--disable-setuid-sandbox",
            "--disable-gpu"
        ]
    )

    context = browser.new_context(
        locale="id-ID",
        timezone_id="Asia/Jakarta",
        viewport={"width": 1366, "height": 768},
        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/139.0.0.0 Safari/537.36"
    )

    page = context.new_page()

    page.set_extra_http_headers({
        "Accept-Language": "id-ID,id;q=0.9,en;q=0.8"
    })
