import os
import json
import gspread
import requests
from google.oauth2.service_account import Credentials
from datetime import datetime

# Google Credentials dari GitHub Secret
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

# Buka Google Sheet
sheet = client.open_by_key(os.environ["SHEET_ID"])

try:
    worksheet = sheet.worksheet("PriceLog")
except:
    worksheet = sheet.sheet1

# Data test
timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

row = [
    timestamp,
    "TEST-DPS-GTO",
    "999999",
    "GitHub Test"
]

worksheet.append_row(row)

# Kirim Telegram
message = f"""✅ Flight Monitor Test

Time:
{timestamp}

Google Sheet berhasil diupdate.
"""

url = f"https://api.telegram.org/bot{os.environ['TELEGRAM_BOT_TOKEN']}/sendMessage"

requests.post(
    url,
    json={
        "chat_id": os.environ["TELEGRAM_CHAT_ID"],
        "text": message
    }
)

print("Success")
