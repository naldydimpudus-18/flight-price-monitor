import os
import json
import re
from datetime import datetime

import gspread
import requests

from oauth2client.service_account import ServiceAccountCredentials
from playwright.sync_api import sync_playwright

# ==========================
# GOOGLE SHEETS
# ==========================

scope = [
    "https://spreadsheets.google.com/feeds",
    "https://www.googleapis.com/auth/drive"
]

creds_json = json.loads(os.environ["GOOGLE_CREDENTIALS"])

creds = ServiceAccountCredentials.from_json_keyfile_dict(
    creds_json,
    scope
)

client = gspread.authorize(creds)

sheet = client.open_by_key(
    os.environ["SHEET_ID"]
)

routes_ws = sheet.worksheet("Routes")
price_ws = sheet.worksheet("PriceLog")

# ==========================
# TELEGRAM
# ==========================

BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]

# ==========================
# EXCHANGE RATE
# ==========================

USD_TO_IDR = 16500

# ==========================
# READ ROUTES
# ==========================

routes = routes_ws.get_all_records()

message = "✈️ Flight Monitor\n\n"

# ==========================
# CHECK ROUTES
# ==========================

with sync_playwright() as p:

    browser = p.chromium.launch(headless=True)

    page = browser.new_page()

    for row in routes:

        route = row["Route"]
        origin = row["Origin"]
        destination = row["Destination"]
        flight_date = row["FlightDate"]

        url = (
            f"https://www.google.com/travel/flights?"
            f"hl=en"
        )

        print(f"Checking {route}")

        search_url = (
            f"https://www.google.com/travel/flights/search?"
            f"tfs=CBwQAhokEgoyMDI2LTEyLTIxag0IAhIJL20vMDJuYmgxcgcIARID{destination}QAFIAXABggELCP___________wGYAQI"
        )

        page.goto(
            search_url,
            wait_until="networkidle",
            timeout=120000
        )

        text = page.locator("body").inner_text()

        match = re.search(r"\$(\d+)", text)

        if match:

            usd_price = int(match.group(1))

            idr_price = usd_price * USD_TO_IDR

            print(
                f"{route} : Rp {idr_price:,}"
            )

            timestamp = datetime.now().strftime(
                "%Y-%m-%d %H:%M:%S"
            )

            price_ws.append_row([
                timestamp,
                route,
                idr_price
            ])

            message += (
                f"{route}\n"
                f"Rp {idr_price:,.0f}\n\n"
            )

        else:

            print(
                f"{route} : PRICE NOT FOUND"
            )

            message += (
                f"{route}\n"
                f"Harga tidak ditemukan\n\n"
            )

    browser.close()

# ==========================
# SEND TELEGRAM
# ==========================

requests.post(
    f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
    data={
        "chat_id": CHAT_ID,
        "text": message
    }
)

print("DONE")
