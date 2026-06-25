import datetime
import os
import json
import requests
import re
import time
import gspread
import pandas as pd
from google.oauth2.service_account import Credentials
from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup

# --- Discord & Google API 設定 ---
DISCORD_WEBHOOK_URL = "https://discord.com/api/webhooks/1519208175646019586/Q_K_CGbqiHIkMtgKQzMLvWFlFGSIN0tr7lGCs88d_kxM5EmmB-GvPxjh3j8xfqpAyzeT"
JSON_CREDS_FILE = "creds.json" 
SPREADSHEET_NAME = "遊々亭雲端監控資料庫"

# --- 認證邏輯 (支援雲端環境變數與本地實體檔案) ---
def get_gspread_client():
    scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    gcp_creds_json = os.environ.get("GCP_CREDENTIALS")

    if gcp_creds_json:
        print("☁️ 偵測到環境變數，使用雲端憑證登入 Google Sheets...")
        creds_dict = json.loads(gcp_creds_json)
        creds = Credentials.from_service_account_info(creds_dict, scopes=scope)
    else:
        print("💻 未偵測到環境變數，使用本地 creds.json 登入 Google Sheets...")
        creds = Credentials.from_service_account_file(JSON_CREDS_FILE, scopes=scope)
        
    return gspread.authorize(creds)

def scrape_yuyutei_page(url):
    cards_data = []
    current_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    with sync_playwright() as p:
        # 在雲端環境中 headless 必須為 True
        browser = p.chromium.launch(headless=True) 
        page = browser.new_page()
        page.set_extra_http_headers({"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"})
        try:
            page.goto(url, timeout=60000)
            page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            try: page.locator("span.border-dark").first.wait_for(state="visible", timeout=15000)
            except: pass
            page.wait_for_timeout(2000)
            
            soup = BeautifulSoup(page.content(), "html.parser")
            cards = soup.select('div.card-product')
            for index, card in enumerate(cards):
                try:
                    card_id_tag = card.select_one('span.border-dark')
                    if not card_id_tag: continue
                    card_id = card_id_tag.text.strip()
                    name = card.select_one('h4.text-primary').text.strip() if card.select_one('h4.text-primary') else "未知卡名"
                    
                    price_tag = card.select_one('strong.text-end')
                    price = 0
                    if price_tag:
                        price_str = re.sub(r'[^\d]', '', price_tag.text)
                        if price_str: price = int(price_str)
                    if price < 1000: continue
                    
                    stock_tag = card.select_one('label.cart_sell_zaiko')
                    stock_status = stock_tag.text.replace("在庫", "").replace(":", "").strip() if stock_tag else "未知"
                    if 'sold-out' in card.get('class', []): stock_status = "×"
                    
                    header = card.find_previous(["h2", "h3"])
                    rarity = header.text.replace("Card List", "").strip() if header else "未知"
                    
                    cards_data.append([current_time, url, card_id, name, rarity, price, stock_status, index])
                except: continue
        except Exception as e: print(f"讀取錯誤 {url}: {e}")
        finally: browser.close()
    return cards_data

def main():
    client = get_gspread_client()
    spreadsheet = client.open(SPREADSHEET_NAME)
    
    # 讀取網址
    url_sheet = spreadsheet.worksheet("ListConfig")
    all_urls_raw = url_sheet.col_values(2)[1:] 
    urls = list(set([u.strip() for u in all_urls_raw if u.strip() != ""]))
    
    if not urls:
        print("目前沒有任何監控網址。")
        return
        
    # 讀取歷史紀錄
    history_sheet = spreadsheet.worksheet("PriceHistory")
    history_data = history_sheet.get_all_records()
    # 修正：補上 SortIndex，確保新建立的表欄位能跟爬取的 8 個值對齊
    history_df = pd.DataFrame(history_data) if history_data else pd.DataFrame(columns=["Timestamp", "URL", "CardID", "Name", "Rarity", "Price", "Stock", "SortIndex"])
    
    all_new_rows = []
    updated_cards_list = []
    
    print(f"開始執行，共 {len(urls)} 個網址...")
    for url in urls:
        cards_list = scrape_yuyutei_page(url)
        for row in cards_list:
            all_new_rows.append(row)
            card_id, rarity, current_price = row[2], row[4], row[5]
            if not history_df.empty:
                card_hist = history_df[(history_df["CardID"] == card_id) & (history_df["Rarity"] == rarity)]
                if not card_hist.empty:
                    old_price = int(card_hist.sort_values(by="Timestamp", ascending=False).iloc[0]["Price"])
                    if current_price != old_price:
                        status = "🔺上漲" if current_price > old_price else "🔻下跌"
                        change = ((current_price - old_price) / old_price) * 100
                        updated_cards_list.append(f" - {row[3]} ({card_id}/{rarity}): {status} {old_price}➔{current_price}円 ({change:+.1f}%)")

    # 寫入雲端與發送通知
    if all_new_rows:
        history_sheet.append_rows(all_new_rows)
        
    if DISCORD_WEBHOOK_URL:
        msg = "🔄 **已完成雲端價格同步**\n" + ("\n".join(updated_cards_list) if updated_cards_list else "✅ 此次盤面無任何變動。")
        requests.post(DISCORD_WEBHOOK_URL, json={"content": msg})
    print("同步完成！")

if __name__ == "__main__":
    main()