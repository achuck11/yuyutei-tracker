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
        spreadsheet_key = "請填入你試算表網址中的那一長串KEY"
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
        # 找出該卡片的所有歷史紀錄
        history = sub_df[(sub_df["CardID"] == row["CardID"]) & 
                         (sub_df["Rarity"] == row["Rarity"])].sort_values("Timestamp")
        
        # 轉換為字典以確保保留所有原始欄位 (包含 SortIndex)
        new_row = row.to_dict()
        
        start_date = history.iloc[0]["Timestamp"][:10]
        initial_price = history.iloc[0]["Price"]
        current_price = row["Price"]
        
        total_change = ((current_price - initial_price) / initial_price) * 100 if initial_price > 0 else 0
        
        new_row["監控起始"] = start_date
        new_row["總漲幅"] = f"{total_change:+.1f}%"
        results.append(new_row)
    return pd.DataFrame(results)

# 載入資料
config_df, df = load_data()

if not df.empty and not config_df.empty:
    display_names = config_df["DisplayName"].tolist()
    tabs = st.tabs(display_names)
    
    for tab, (_, row) in zip(tabs, config_df.iterrows()):
        with tab:
            st.caption(f"🔗 來源網址: {row['URL']}")
            sub_df = df[df["URL"] == row["URL"]].copy()
            
            # 強制轉型，確保排序依據是數字
            sub_df["SortIndex"] = pd.to_numeric(sub_df["SortIndex"], errors='coerce')
            sub_df["Price"] = pd.to_numeric(sub_df["Price"], errors='coerce')
            
            # 分組取最新值 (as_index=False 確保 SortIndex 保留在 DataFrame 中)
            latest = sub_df.sort_values("Timestamp").groupby(["CardID", "Rarity", "SortIndex"], as_index=False).last()
            
            # 計算趨勢
            latest = process_trend_data(sub_df, latest)
            
            # 排序
            latest = latest.sort_values("SortIndex")
            
            # 顯示表格 (使用新版 width='stretch' 參數)
            st.dataframe(
                latest[["CardID", "Name", "Rarity", "Price", "監控起始", "總漲幅", "Stock"]], 
                width=None, # 設定為 None 會自動隨容器寬度伸展
                hide_index=True
            )
else:
    st.info("雲端資料庫目前無資料，請確認爬蟲已執行並寫入 'PriceHistory' (含 SortIndex 欄位)。")