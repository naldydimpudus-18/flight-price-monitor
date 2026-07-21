from playwright.sync_api import sync_playwright
import gspread
from google.oauth2.service_account import Credentials
import os
import json
import re
from datetime import datetime

# =====================
# GOOGLE SHEETS LOGIN
# =====================

creds_dict = json.loads(os.environ["GOOGLE_CREDENTIALS"])

scopes = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]

creds = Credentials.from_service_account_info(
    creds_dict,
    scopes=scopes
)

client = gspread.authorize(creds)

sheet = client.open_by_key(os.environ["SHEET_ID"])

routes_ws = sheet.worksheet("Routes")
pricelog_ws = sheet.worksheet("PriceLog")

# =====================
# GOOGLE FLIGHTS CHECK
# =====================

URLS = {
    "DPS-GTO": "https://www.google.com/travel/flights/search?tfs=CBwQAhokEgoyMDI2LTEyLTIxag0IAhIJL20vMDJuYmgxcgcIARIDR1RPQAFIAXABggELCP___________wGYAQI",
    "DPS-MDC": "https://www.google.com/travel/flights/search?tfs=CBwQAhokEgoyMDI2LTEyLTIxag0IAhIJL20vMDJuYmgxcgcIARIDTURDQAFIAXABggELCP___________wGYAQI&tfu=EgYIABAAGAA",
    "DPS-PLW": "https://www.google.com/travel/flights/search?tfs=CBwQAhokEgoyMDI2LTEyLTIxag0IAhIJL20vMDJuYmgxcgcIARIDUExXQAFIAXABggELCP___________wGYAQI&tfu=EgYIABAAGAA"
}

with sync_playwright() as p:

    browser = p.chromium.launch(headless=True)

    for route, url in URLS.items():

        page = browser.new_page()

        print(f"Checking {route}")

        page.goto(
            url,
            wait_until="networkidle",
            timeout=120000
        )

        text = page.locator("body").inner_text()

        match = re.search(r"\$(\d+)", text)

        if match:

            usd_price = int(match.group(1))

            idr_price = usd_price * 16500

            timestamp = datetime.now().strftime(
                "%Y-%m-%d %H:%M:%S"
            )

            pricelog_ws.append_row([
                timestamp,
                route,
                usd_price,
                idr_price
            ])

            print(
                f"{route} : USD {usd_price} | IDR {idr_price}"
            )

        else:

            print(
                f"{route} : PRICE NOT FOUND"
            )

        page.close()

    browser.close()
