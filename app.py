import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials

st.set_page_config(page_title="遊々亭 雲端共用監控清單", layout="wide")
st.title("🃏 遊々亭 雲端共用監控清單 (>= 1000円)")

@st.cache_data(ttl=300)
def load_data():
    try:
        # 從 Secrets 讀取憑證
        creds_dict = st.secrets["gcp_service_account"]
        creds = Credentials.from_service_account_info(
            creds_dict, 
            scopes=["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
        )
        client = gspread.authorize(creds)
        
        # 使用精準的 Key 存取試算表
        # 請將下面這串字換成你網址中的 Key (例如: 1AbCdEfGhIjKlMnOpQrStUvWxYz)
        spreadsheet_key = "請填入你試算表網址中的那一長串KEY"
        spreadsheet = client.open_by_key(spreadsheet_key)
        
        # 讀取資料
        history_sheet = spreadsheet.worksheet("PriceHistory")
        data = history_sheet.get_all_records()
        
        if not data:
            return pd.DataFrame()
            
        return pd.DataFrame(data)
    except Exception as e:
        st.error(f"連線或讀取失敗，詳細錯誤: {e}")
        return pd.DataFrame()

# 顯示介面
with st.spinner("正在從雲端載入最新卡價..."):
    df = load_data()

if not df.empty:
    # 按照網址分類成多個分頁顯示
    urls = df["URL"].unique()
    tabs = st.tabs([f"監控清單 {i+1}" for i in range(len(urls))])
    
    for tab, url in zip(tabs, urls):
        with tab:
            st.caption(f"🔗 來源網址: {url}")
            sub_df = df[df["URL"] == url].copy()
            
            # 轉換時間格式與處理價格
            sub_df["Price"] = pd.to_numeric(sub_df["Price"])
            
            # 取得每張卡片最新一筆紀錄
            latest_records = sub_df.sort_values("Timestamp").groupby(["CardID", "Rarity"]).last().reset_index()
            
            # 簡單計算漲跌 (若有歷史數據)
            latest_records["近期趨勢"] = "更新中"
            
            # 呈現表格
            display_cols = ["Timestamp", "CardID", "Name", "Rarity", "Price", "Stock", "近期趨勢"]
            st.dataframe(latest_records[display_cols], use_container_width=True, hide_index=True)
else:
    st.info("雲端資料庫目前沒有資料，請確認本地爬蟲已成功執行並上傳數據。")