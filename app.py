import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials

st.set_page_config(page_title="遊々亭 雲端共用監控清單", layout="wide")
st.title("🃏 遊々亭 雲端共用監控清單 (>= 1000円)")

@st.cache_data(ttl=300)
def load_data():
    try:
        creds_dict = st.secrets["gcp_service_account"]
        creds = Credentials.from_service_account_info(
            creds_dict, 
            scopes=["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
        )
        client = gspread.authorize(creds)
        
        # 請填入你真實的試算表 KEY
        spreadsheet_key = "1KeCPC0fEYiZB4_bWvFcroePVrt8XS1Uu3HrKMaRfW_Y"
        spreadsheet = client.open_by_key(spreadsheet_key)
        
        # 讀取設定與資料
        config_data = spreadsheet.worksheet("ListConfig").get_all_records()
        history_data = spreadsheet.worksheet("PriceHistory").get_all_records()
        
        return pd.DataFrame(config_data), pd.DataFrame(history_data)
    except Exception as e:
        st.error(f"連線或讀取失敗: {e}")
        return pd.DataFrame(), pd.DataFrame()

# 載入資料
config_df, df = load_data()

if not df.empty and not config_df.empty:
    # 按照 ListConfig 設定的 DisplayName 產生分頁
    display_names = config_df["DisplayName"].tolist()
    tabs = st.tabs(display_names)
    
    for tab, (_, row) in zip(tabs, config_df.iterrows()):
        with tab:
            st.caption(f"🔗 來源網址: {row['URL']}")
            sub_df = df[df["URL"] == row["URL"]].copy()
            
            # 確保 SortIndex 為數值，以便正確排序
            sub_df["SortIndex"] = pd.to_numeric(sub_df["SortIndex"], errors='coerce')
            sub_df["Price"] = pd.to_numeric(sub_df["Price"], errors='coerce')
            
            # 取得該網址下，每張卡片最新的一筆數據
            latest = sub_df.sort_values("Timestamp").groupby(["CardID", "Rarity"]).last().reset_index()
            
            # 依照爬蟲記錄下來的網頁原始順序排序
            latest = latest.sort_values("SortIndex")
            
            # 顯示表格 (隱藏內部運算的 SortIndex 欄位)
            st.dataframe(
                latest[["CardID", "Name", "Rarity", "Price", "Stock"]], 
                use_container_width=True, 
                hide_index=True
            )
else:
    st.info("雲端資料庫目前無資料，請確認爬蟲已執行並寫入 'PriceHistory' (含 SortIndex 欄位)。")