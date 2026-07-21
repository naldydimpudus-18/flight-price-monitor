import os
import re
import json
import time
import urllib.parse
from datetime import datetime

import gspread
import requests
from oauth2client.service_account import ServiceAccountCredentials
from playwright.sync_api import sync_playwright, TimeoutError as PWTimeoutError

# ==========================
# CONFIG
# ==========================
SCOPE = [
    "https://spreadsheets.google.com/feeds",
    "https://www.googleapis.com/auth/drive",
]

ROUTES_SHEET_NAME = "Routes"
PRICELOG_SHEET_NAME = "PriceLog"

# Google Flights locale/currency — we force IDR so we don't need to
# do manual USD -> IDR conversion (avoids stale exchange rate issues).
GFLIGHTS_HL = "id"   # UI language
GFLIGHTS_GL = "ID"   # country
GFLIGHTS_CURR = "IDR"

REQUEST_TIMEOUT_MS = 90_000
PAGE_SETTLE_WAIT_MS = 4_000  # extra wait after load for JS-rendered prices

# Common text used on Google's consent/cookie interstitial (varies by locale)
CONSENT_BUTTON_TEXTS = [
    "Terima semua", "Setuju semua", "Saya setuju",
    "Accept all", "I agree", "Agree to all",
]

PRICE_REGEX = re.compile(r"Rp\s?([\d.,]+)")


def log(msg):
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {msg}")


# ==========================
# GOOGLE SHEETS
# ==========================
def connect_sheets():
    creds_json = json.loads(os.environ["GOOGLE_CREDENTIALS"])
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_json, SCOPE)
    client = gspread.authorize(creds)
    sheet = client.open_by_key(os.environ["SHEET_ID"])
    log(f"Connected to sheet: {sheet.title}")

    routes_ws = sheet.worksheet(ROUTES_SHEET_NAME)
    price_ws = sheet.worksheet(PRICELOG_SHEET_NAME)
    return routes_ws, price_ws


def get_last_price(price_ws, route):
    """Return the most recent logged price (int) for a route, or None."""
    try:
        records = price_ws.get_all_values()
    except Exception as e:
        log(f"Could not read PriceLog for comparison: {e}")
        return None

    # Expect columns: Timestamp, Route, Price  (skip header row)
    for row in reversed(records[1:]):
        if len(row) >= 3 and row[1] == route:
            try:
                return int(str(row[2]).replace(".", "").replace(",", ""))
            except ValueError:
                continue
    return None


# ==========================
# SCRAPER
# ==========================
def build_search_url(origin, destination, flight_date):
    query = f"Flights from {origin} to {destination} on {flight_date}"
    encoded = urllib.parse.quote(query)
    return (
        f"https://www.google.com/travel/flights?q={encoded}"
        f"&hl={GFLIGHTS_HL}&gl={GFLIGHTS_GL}&curr={GFLIGHTS_CURR}"
    )


def dismiss_consent_if_present(page):
    for text in CONSENT_BUTTON_TEXTS:
        try:
            btn = page.get_by_role("button", name=text, exact=False)
            if btn.count() > 0:
                btn.first.click(timeout=3000)
                page.wait_for_timeout(1500)
                return True
        except Exception:
            continue
    return False


def extract_lowest_price(page, debug_name=None):
    """
    Extraction scoped to flight result cards (role='listitem'), NOT the
    whole page body. Scanning the whole page picks up unrelated 'Rp'
    numbers from ads, insurance/baggage add-ons, promo banners, etc,
    which is the most common cause of wrong prices. Scoping to result
    cards is much more reliable.
    """
    cards = page.locator("li[role='listitem']")
    count = cards.count()

    prices = []
    for i in range(min(count, 30)):
        try:
            card_text = cards.nth(i).inner_text(timeout=2000)
        except Exception:
            continue
        for m in PRICE_REGEX.findall(card_text):
            cleaned = m.replace(".", "").replace(",", "")
            if cleaned.isdigit():
                prices.append(int(cleaned))

    # Fallback: if no list items found at all (Google changed the DOM,
    # or the page didn't render results), fall back to whole-page scan
    # so we still get *something* rather than nothing.
    if not prices:
        text = page.locator("body").inner_text()
        for m in PRICE_REGEX.findall(text):
            cleaned = m.replace(".", "").replace(",", "")
            if cleaned.isdigit():
                prices.append(int(cleaned))

    # Save a screenshot + raw text dump for debugging, always.
    if debug_name:
        try:
            os.makedirs("debug", exist_ok=True)
            page.screenshot(path=f"debug/{debug_name}.png", full_page=True)
            with open(f"debug/{debug_name}.txt", "w", encoding="utf-8") as f:
                f.write(page.locator("body").inner_text())
        except Exception as e:
            log(f"Failed to save debug artifacts for {debug_name}: {e}")

    if not prices:
        return None

    return min(prices)


def scrape_route(page, origin, destination, flight_date, debug_name=None):
    url = build_search_url(origin, destination, flight_date)
    log(f"Opening: {url}")

    page.goto(url, wait_until="domcontentloaded", timeout=REQUEST_TIMEOUT_MS)

    dismiss_consent_if_present(page)

    try:
        page.wait_for_load_state("networkidle", timeout=REQUEST_TIMEOUT_MS)
    except PWTimeoutError:
        log("networkidle timeout — continuing anyway, page may still have rendered results")

    page.wait_for_timeout(PAGE_SETTLE_WAIT_MS)

    return extract_lowest_price(page, debug_name=debug_name)


# ==========================
# TELEGRAM
# ==========================
def send_telegram_message(text):
    bot_token = os.environ["TELEGRAM_BOT_TOKEN"]
    chat_id = os.environ["TELEGRAM_CHAT_ID"]

    try:
        response = requests.post(
            f"https://api.telegram.org/bot{bot_token}/sendMessage",
            data={"chat_id": chat_id, "text": text},
            timeout=30,
        )
        log(f"Telegram response: {response.status_code} {response.text}")
    except Exception as e:
        log(f"Failed to send Telegram message: {e}")


def format_price_line(route, price, last_price):
    line = f"✈️ {route}\nRp {price:,.0f}"
    if last_price is not None:
        diff = price - last_price
        if diff > 0:
            line += f"\n📈 Naik Rp {diff:,.0f} dari cek terakhir"
        elif diff < 0:
            line += f"\n📉 Turun Rp {abs(diff):,.0f} dari cek terakhir"
        else:
            line += "\n➖ Tidak ada perubahan harga"
    return line + "\n"


# ==========================
# MAIN
# ==========================
def main():
    routes_ws, price_ws = connect_sheets()

    routes = routes_ws.get_all_records()
    log(f"Found {len(routes)} route(s) to check")

    message_lines = ["🛫 Flight Price Monitor", ""]
    any_success = False

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
            viewport={"width": 1366, "height": 900},
            locale="id-ID",
        )
        page = context.new_page()

        for row in routes:
            route = row.get("Route", "").strip()
            origin = row.get("Origin", "").strip()
            destination = row.get("Destination", "").strip()
            flight_date = row.get("FlightDate", "").strip()

            if not route or not origin or not destination or not flight_date:
                log(f"Skipping incomplete row: {row}")
                continue

            log(f"--- Checking {route} ---")

            safe_name = re.sub(r"[^a-zA-Z0-9_-]", "_", route)
            try:
                price = scrape_route(page, origin, destination, flight_date, debug_name=safe_name)
            except Exception as e:
                log(f"Error while checking {route}: {e}")
                message_lines.append(f"⚠️ {route}\nGagal cek harga ({e.__class__.__name__})\n")
                continue

            if price is None:
                log(f"{route}: price not found")
                message_lines.append(f"⚠️ {route}\nHarga tidak ditemukan\n")
                continue

            last_price = get_last_price(price_ws, route)

            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            try:
                price_ws.append_row([timestamp, route, price])
                log(f"{route}: Rp {price:,} — logged to PriceLog")
            except Exception as e:
                log(f"Failed to write to PriceLog for {route}: {e}")

            message_lines.append(format_price_line(route, price, last_price))
            any_success = True

        browser.close()

    if not any_success:
        message_lines.append("Tidak ada harga yang berhasil diambil pada run ini.")

    final_message = "\n".join(message_lines)
    send_telegram_message(final_message)
    log("DONE")


if __name__ == "__main__":
    main()
