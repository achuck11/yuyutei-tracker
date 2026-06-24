import streamlit as st
import pandas as pd
import gspread
import datetime
from oauth2client.service_account import ServiceAccountCredentials

st.set_page_config(page_title="遊々亭雲端卡價監控站", layout="wide")
st.title("🃏 遊々亭 雲端共用監控清單 (>= 1000円)")

# 從 Streamlit 雲端後台安全地讀取憑證 (Secrets)
creds_dict = st.secrets["gcp_service_account"]
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
client = gspread.authorize(creds)

@st.cache_data(ttl=300) # 快取 5 分鐘，避免過度頻繁讀取 Google API 導致超限
def load_data():
    try:
        spreadsheet = client.open("遊々亭雲端監控資料庫")
        history_sheet = spreadsheet.worksheet("PriceHistory")
        data = history_sheet.get_all_records()
        return pd.DataFrame(data)
    except Exception as e:
        st.error(f"資料庫讀取失敗: {e}")
        return pd.DataFrame()

df = load_data()

if not df.empty:
    # 按照網址分類成多個分頁顯示
    urls = df["URL"].unique()
    tabs = st.tabs([f"監控清單 {i+1}" for i in range(len(urls))])
    
    for tab, url in zip(tabs, urls):
        with tab:
            st.caption(f"🔗 來源網址: {url}")
            sub_df = df[df["URL"] == url]
            
            # 取得每張卡片最新一筆紀錄
            latest_records = sub_df.sort_values("Timestamp").groupby(["CardID", "Rarity"]).last().reset_index()
            three_days_ago = datetime.datetime.now() - datetime.timedelta(days=3)
            trends = []
            
            for _, row in latest_records.iterrows():
                card_hist = sub_df[(sub_df["CardID"] == row["CardID"]) & (sub_df["Rarity"] == row["Rarity"])].copy()
                card_hist_past = card_hist[card_hist["Timestamp"] != row["Timestamp"]].copy()
                
                if not card_hist_past.empty:
                    card_hist_past["Timestamp_dt"] = pd.to_datetime(card_hist_past["Timestamp"])
                    in_window = card_hist_past[card_hist_past["Timestamp_dt"] >= three_days_ago]
                    old_p = in_window.sort_values("Timestamp_dt").iloc[0]["Price"] if not in_window.empty else card_hist_past.sort_values("Timestamp_dt").iloc[-1]["Price"]
                    
                    if old_p > 0:
                        change = ((row["Price"] - old_p) / old_p) * 100
                        trends.append("持平" if change == 0 else f"{change:+.1f}%")
                    else: trends.append("無效原價")
                else: trends.append("新快照")
                    
            latest_records["近期趨勢"] = trends

            # 動態稀有度排序邏輯
            latest_time = sub_df["Timestamp"].max()
            latest_scrape = sub_df[sub_df["Timestamp"] == latest_time]
            dynamic_rarity_list = latest_scrape["Rarity"].drop_duplicates().tolist()
            for r in latest_records["Rarity"].unique():
                if r not in dynamic_rarity_list: dynamic_rarity_list.append(r)
            dynamic_rarity_dict = {r: i for i, r in enumerate(dynamic_rarity_list)}
            
            latest_records["Rarity_Rank"] = latest_records["Rarity"].map(dynamic_rarity_dict)
            latest_records = latest_records.sort_values(by=["Rarity_Rank", "Price"], ascending=[True, False])

            def highlight_changes(val):
                if isinstance(val, str) and "%" in val:
                    num = float(val.replace("%", "").replace("+", ""))
                    if num > 0: return 'background-color: #ffcccc; font-weight: bold; color: #d32f2f;'
                    elif num < 0: return 'background-color: #e8f5e9; font-weight: bold; color: #2e7d32;'
                return ''

            display_cols = ["Timestamp", "CardID", "Name", "Rarity", "Price", "Stock", "近期趨勢"]
            styled_df = latest_records[display_cols].style.applymap(highlight_changes, subset=["近期趨勢"])
            st.dataframe(styled_df, use_container_width=True, hide_index=True)
else:
    st.info("雲端資料庫目前沒有卡片歷史資料，請確保本地爬蟲已成功同步資料至 Google Sheets。")