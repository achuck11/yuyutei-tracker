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
        
        config_data = spreadsheet.worksheet("ListConfig").get_all_records()
        history_data = spreadsheet.worksheet("PriceHistory").get_all_records()
        
        return pd.DataFrame(config_data), pd.DataFrame(history_data)
    except Exception as e:
        st.error(f"連線或讀取失敗: {e}")
        return pd.DataFrame(), pd.DataFrame()

# 計算趨勢與監控起始日的邏輯
def process_trend_data(sub_df, latest):
    results = []
    for _, row in latest.iterrows():
        history = sub_df[(sub_df["CardID"] == row["CardID"]) & 
                         (sub_df["Rarity"] == row["Rarity"])].sort_values("Timestamp")
        
        start_date = history.iloc[0]["Timestamp"][:10]
        initial_price = history.iloc[0]["Price"]
        current_price = row["Price"]
        
        # 計算總漲幅
        total_change = ((current_price - initial_price) / initial_price) * 100 if initial_price > 0 else 0
        
        row["監控起始"] = start_date
        row["總漲幅"] = f"{total_change:+.1f}%"
        results.append(row)
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
            
            # 確保欄位數值化 (放在最前面以免出錯)
            sub_df["SortIndex"] = pd.to_numeric(sub_df["SortIndex"], errors='coerce')
            sub_df["Price"] = pd.to_numeric(sub_df["Price"], errors='coerce')

            # 【修正關鍵】：將 SortIndex 加入 groupby 清單，並確保它不被丟棄
            latest = sub_df.sort_values("Timestamp").groupby(["CardID", "Rarity", "SortIndex"], as_index=False).last()
            
            # 處理趨勢與日期顯示 (這函數會回傳包含所有欄位的 DataFrame)
            latest = process_trend_data(sub_df, latest)
            
            # 【修正關鍵】：現在 DataFrame 一定會有 SortIndex，排序就不會報錯了
            latest = latest.sort_values("SortIndex")
            
            # 顯示表格
            st.dataframe(
                latest[["CardID", "Name", "Rarity", "Price", "監控起始", "總漲幅", "Stock"]], 
                use_container_width=True, 
                hide_index=True
            )
else:
    st.info("雲端資料庫目前無資料，請確認爬蟲已執行並寫入 'PriceHistory'。")