import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials

st.set_page_config(page_title="遊々亭 雲端共用監控清單", layout="wide")
st.title("🃏 遊々亭 雲端共用監控清單 (>= 1000円)")

# 定義稀有度權重，確保排序穩定 (數值越小越前面)
RARITY_PRIORITY = {
    "SEC": 1, "SSP": 2, "SP": 3, "SR": 4, "RRR": 5, "RR": 6, "R": 7, 
    "HR": 1, "GA": 2, "MR": 3, "PR": 10
}

@st.cache_data(ttl=300)
def load_data():
    try:
        creds_dict = st.secrets["gcp_service_account"]
        creds = Credentials.from_service_account_info(
            creds_dict, 
            scopes=["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
        )
        client = gspread.authorize(creds)
        
        # 請確保這裡的 KEY 是正確的
        spreadsheet_key = "1KeCPC0fEYiZB4_bWvFcroePVrt8XS1Uu3HrKMaRfW_Y"
        spreadsheet = client.open_by_key(spreadsheet_key)
        
        config_data = spreadsheet.worksheet("ListConfig").get_all_records()
        history_data = spreadsheet.worksheet("PriceHistory").get_all_records()
        
        return pd.DataFrame(config_data), pd.DataFrame(history_data)
    except Exception as e:
        st.error(f"連線或讀取失敗: {e}")
        return pd.DataFrame(), pd.DataFrame()

def process_trend_data(sub_df, latest):
    results = []
    for _, row in latest.iterrows():
        history = sub_df[(sub_df["CardID"] == row["CardID"]) & 
                         (sub_df["Rarity"] == row["Rarity"])].sort_values("Timestamp")
        
        new_row = row.to_dict()
        
        start_date = history.iloc[0]["Timestamp"][:10]
        initial_price = history.iloc[0]["Price"]
        current_price = row["Price"]
        
        total_change = ((current_price - initial_price) / initial_price) * 100 if initial_price > 0 else 0
        
        new_row["監控起始"] = start_date
        new_row["總漲幅"] = f"{total_change:+.1f}%"
        results.append(new_row)
    return pd.DataFrame(results)

config_df, df = load_data()

if not df.empty and not config_df.empty:
    display_names = config_df["DisplayName"].tolist()
    tabs = st.tabs(display_names)
    
    for tab, (_, row) in zip(tabs, config_df.iterrows()):
        with tab:
            st.caption(f"🔗 來源網址: {row['URL']}")
            sub_df = df[df["URL"] == row["URL"]].copy()
            sub_df["Price"] = pd.to_numeric(sub_df["Price"], errors='coerce')
            
            # 取出每張卡片的最新一筆數據
            latest = sub_df.sort_values("Timestamp").drop_duplicates(subset=["CardID", "Rarity"], keep="last")
            
            # 計算趨勢
            latest = process_trend_data(sub_df, latest)
            
            # 排序邏輯：透過字典映射稀有度權重，不再依賴 SortIndex
            latest["Priority"] = latest["Rarity"].map(RARITY_PRIORITY).fillna(99)
            latest = latest.sort_values("Priority")
            
            # 顯示表格
            st.dataframe(
                latest[["CardID", "Name", "Rarity", "Price", "監控起始", "總漲幅", "Stock"]], 
                width='stretch', 
                hide_index=True
            )
else:
    st.info("雲端資料庫目前無資料，請確認爬蟲已執行。")