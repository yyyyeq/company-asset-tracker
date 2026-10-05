import streamlit as st
import pandas as pd
from datetime import datetime
from supabase import create_client, Client

st.set_page_config(
    page_title="資產管理系統",
    page_icon="💻",
    layout="wide"
)

# 取得 Supabase 連線
@st.cache_resource
def init_supabase() -> Client:
    url = st.secrets["SUPABASE_URL"]
    key = st.secrets["SUPABASE_KEY"]
    return create_client(url, key)

try:
    supabase = init_supabase()
except Exception as e:
    st.error("❌ 連線 Supabase 失敗，請檢查 Streamlit Secrets 設定！")
    st.stop()

# 常用選項定義
ASSET_TYPES = ["全部", "固定資產", "低值品", "物料", "樣機", "外購機"]
RAW_ASSET_TYPES = ["固定資產", "低值品", "物料", "樣機", "外購機"]
STATUS_OPTIONS = ["全部", "在庫", "使用中", "借測中", "維修中", "報廢"]

# 側邊欄導航
st.sidebar.title("🏢 資產管理資料庫")
menu = st.sidebar.radio(
    "功能模組",
    ["📊 統計總覽", "📋 資產清單與查詢", "🔄 設備借還/異動移交", "➕ 單筆新增資產", "📥 批次匯入 (Excel/CSV)"]
)

# ----------------- 模組 1: 統計總覽 -----------------
if menu == "📊 統計總覽":
    st.header("資產即時概況")
    res = supabase.table("assets").select("*").execute()
    df = pd.DataFrame(res.data)

    if not df.empty:
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("總資產數", len(df))
        col2.metric("在庫可用", len(df[df["status"] == "在庫"]))
        col3.metric("使用/借測中", len(df[df["status"].isin(["使用中", "借測中"])]))
        col4.metric("維修/報廢", len(df[df["status"].isin(["維修中", "報廢"])]))

        st.divider()
        c1, c2 = st.columns(2)
        with c1:
            st.subheader("資產類型分佈 (固定資產/樣機/物料等)")
            if "asset_type" in df.columns:
                type_counts = df["asset_type"].fillna("未分類").value_counts()
                st.bar_chart(type_counts)
        with c2:
            st.subheader("設備類別分佈")
            cat_counts = df["category"].fillna("未分類").value_counts()
            st.bar_chart(cat_counts)
    else:
        st.info("目前資料庫內尚無資產資料，可透過「單筆新增」或「批次匯入」建立資料。")

# ----------------- 模組 2: 資產清單與查詢 -----------------
elif menu == "📋 資產清單與查詢":
    st.header("資產檢索清單")
    
    # 篩選列
    c1, c2, c3, c4 = st.columns([2, 1, 1, 1])
    search_keyword = c1.text_input("🔍 搜尋 (資產編號 / S/N / 設備名稱 / 保管人)")
    type_filter = c2.selectbox("資產類型", ASSET_TYPES)
    status_filter = c3.selectbox("設備狀態", STATUS_OPTIONS)
    loc_filter = c4.text_input("存放地點 (如: 台北辦公室)")

    query = supabase.table("assets").select("*")
    if type_filter != "全部":
        query = query.eq("asset_type", type_filter)
    if status_filter != "全部":
        query = query.eq("status", status_filter)
    if loc_filter:
        query = query.ilike("location", f"%{loc_filter}%")
    
    data = query.order("created_at", desc=True).execute().data
    df = pd.DataFrame(data)

    if not df.empty:
        if search_keyword:
            mask = (
                df["asset_tag"].astype(str).str.contains(search_keyword, case=False, na=False) |
                df["serial_number"].astype(str).str.contains(search_keyword, case=False, na=False) |
                df["name"].astype(str).str.contains(search_keyword, case=False, na=False) |
                df["holder_name"].astype(str).str.contains(search_keyword, case=False, na=False)
            )
            df = df[mask]

        cols_display = ["asset_tag", "asset_type", "name", "category", "status", "holder_name", "holder_department", "location", "serial_number", "cost"]
        available_cols = [c for c in cols_display if c in df.columns]
        
        st.dataframe(df[available_cols], use_container_width=True, hide_index=True)

        csv = df.to_csv(index=False).encode('utf-8-sig')
        st.download_button("📥 匯出當前清單 (CSV)", csv, "assets_export.csv", "text/csv")
    else:
        st.warning("查無符合條件的資產。")

# ----------------- 模組 3: 設備借還/異動移交 -----------------
elif menu == "🔄 設備借還/異動移交":
    st.header("設備異動與保管人變更")
    
    asset_tag_input = st.text_input("請輸入欲異動的資產編號 (Asset Tag)")
    
    if asset_tag_input:
        res = supabase.table("assets").select("*").eq("asset_tag", asset_tag_input.strip()).execute()
        if res.data:
            asset = res.data[0]
            st.success(f"找到設備：[{asset.get('asset_type', '固定資產')}] {asset['name']} (目前狀態：{asset['status']}，保管人：{asset['holder_name'] or '無'})")
            
            with st.form("transfer_form"):
                action = st.selectbox("異動動作", ["領用配發", "設備借測", "歸還入庫", "送修", "報廢"])
                new_holder = st.text_input("新保管人姓名 (歸還/送修/報廢可留空)")
                new_dept = st.text_input("新保管人部門")
                operator = st.text_input("經辦人姓名", value="Admin")
                remark = st.text_area("備註事由 (如：短期借測、故障維修)")
                
                submitted = st.form_submit_button("確認提交異動")
                if submitted:
                    status_map = {
                        "領用配發": "使用中",
                        "設備借測": "借測中",
                        "歸還入庫": "在庫",
                        "送修": "維修中",
                        "報廢": "報廢"
                    }
                    next_status = status_map[action]
                    target_holder = None if action in ["歸還入庫", "送修", "報廢"] else new_holder
                    target_dept = None if action in ["歸還入庫", "送修", "報廢"] else new_dept
                    
                    supabase.table("assets").update({
                        "status": next_status,
                        "holder_name": target_holder,
                        "holder_department": target_dept,
                        "updated_at": datetime.utcnow().isoformat()
                    }).eq("id", asset["id"]).execute()
                    
                    supabase.table("asset_logs").insert({
                        "asset_id": asset["id"],
                        "asset_tag": asset["asset_tag"],
                        "action_type": action,
                        "previous_holder": asset["holder_name"],
                        "new_holder": target_holder,
                        "operator": operator,
                        "remark": remark
                    }).execute()
                    
                    st.success("✅ 異動成功，資料庫與日誌已即時更新！")
        else:
            st.error("查無此資產編號，請重新確認。")

# ----------------- 模組 4: 單筆新增資產 -----------------
elif menu == "➕ 單筆新增資產":
    st.header("建立新資產資料")
    
    with st.form("new_asset_form"):
        col1, col2 = st.columns(2)
        tag = col1.text_input("資產編號 (必填，如 NB-2026-001)")
        asset_type = col2.selectbox("資產類型 (會計/管理分類)", RAW_ASSET_TYPES)
        name = col1.text_input("設備型號名稱 (必填，如 ThinkPad X1 / iPhone 15)")
        sn = col2.text_input("原廠序號 S/N")
        
        cat_data = supabase.table("asset_categories").select("name").execute().data
        cat_options = [c["name"] for c in cat_data] if cat_data else ["筆記型電腦", "公務機/測試手機", "螢幕", "辦公家具", "耗材與物料"]
        category = col1.selectbox("設備規格分類", cat_options)
        
        location = col2.text_input("存放地點", value="台北辦公室")
        cost = col1.number_input("採購金額", min_value=0.0, step=100.0)
        holder = col2.text_input("初始保管人 (可留空，留空則為在庫)")
        notes = st.text_area("規格與備註說明")
        
        submit_btn = st.form_submit_button("新增至資料庫")
        if submit_btn:
            if not tag or not name:
                st.error("資產編號與設備型號為必填項！")
            else:
                try:
                    init_status = "使用中" if holder else "在庫"
                    insert_res = supabase.table("assets").insert({
                        "asset_tag": tag.strip(),
                        "asset_type": asset_type,
                        "serial_number": sn.strip() if sn else None,
                        "name": name.strip(),
                        "category": category,
                        "status": init_status,
                        "holder_name": holder.strip() if holder else None,
                        "location": location.strip(),
                        "cost": cost,
                        "notes": notes
                    }).execute()
                    
                    if insert_res.data:
                        new_asset = insert_res.data[0]
                        supabase.table("asset_logs").insert({
                            "asset_id": new_asset["id"],
                            "asset_tag": tag.strip(),
                            "action_type": "新增入庫",
                            "operator": "Admin",
                            "remark": f"初始建檔 - 分類: {asset_type}"
                        }).execute()
                    st.success(f"🎉 資產 [{asset_type}] {tag} 建立成功！")
                except Exception as e:
                    st.error(f"建立失敗：{str(e)}")

# ----------------- 模組 5: 批次匯入 (Excel/CSV) -----------------
elif menu == "📥 批次匯入 (Excel/CSV)":
    st.header("批次匯入現有資產資料")
    st.write("支援上傳 `.xlsx` 或 `.csv` 檔案，一次匯入數十至上千筆資產。")
    
    # 下載範本按鈕
    sample_df = pd.DataFrame([{
        "資產編號": "NB-2026-001",
        "設備名稱": "MacBook Pro 14",
        "資產類型": "固定資產",
        "設備分類": "筆記型電腦",
        "原廠序號": "C02XYZ12345",
        "目前狀態": "在庫",
        "保管人": "",
        "保管部門": "",
        "存放地點": "台北辦公室",
        "金額": 45000,
        "規格備註": "M3 Pro / 18G / 512G"
    }, {
        "資產編號": "SP-2026-002",
        "設備名稱": "Pixel 8 測試機",
        "資產類型": "樣機",
        "設備分類": "公務機/測試手機",
        "原廠序號": "FA12345678",
        "目前狀態": "借測中",
        "保管人": "測試小組",
        "保管部門": "研發部",
        "存放地點": "台北辦公室",
        "金額": 18000,
        "規格備註": "專案測試專用"
    }])
    
    csv_sample = sample_df.to_csv(index=False).encode('utf-8-sig')
    st.download_button("📄 下載標準匯入範本 (CSV)", csv_sample, "資產匯入標準範本.csv", "text/csv")
    
    st.divider()
    uploaded_file = st.file_uploader("選擇要匯入的檔案", type=["csv", "xlsx"])
    
    if uploaded_file is not None:
        try:
            if uploaded_file.name.endswith(".csv"):
                upload_df = pd.read_csv(uploaded_file)
            else:
                upload_df = pd.read_excel(uploaded_file)
            
            st.write("預覽上傳資料（前 5 筆）：")
            st.dataframe(upload_df.head(), use_container_width=True)
            
            # 欄位對齊轉換字典
            column_mapping = {
                "資產編號": "asset_tag",
                "設備名稱": "name",
                "資產類型": "asset_type",
                "設備分類": "category",
                "原廠序號": "serial_number",
                "目前狀態": "status",
                "保管人": "holder_name",
                "保管部門": "holder_department",
                "存放地點": "location",
                "規格備註": "notes"
            }
            
            # 檢查必填欄位
            if "資產編號" not in upload_df.columns or "設備名稱" not in upload_df.columns:
                st.error("❌ 檔案缺少必要欄位：「資產編號」或「設備名稱」，請對照範本！")
            else:
                if st.button("🚀 確認將資料整批匯入 Supabase"):
                    # 重新命名欄位
                    upload_df = upload_df.rename(columns=column_mapping)
                    
                    # 確保必要欄位預設值
                    if "asset_type" not in upload_df.columns:
                        upload_df["asset_type"] = "固定資產"
                    else:
                        upload_df["asset_type"] = upload_df["asset_type"].fillna("固定資產")
                        
                    if "status" not in upload_df.columns:
                        upload_df["status"] = "在庫"
                    else:
                        upload_df["status"] = upload_df["status"].fillna("在庫")
                        
                    if "location" not in upload_df.columns:
                        upload_df["location"] = "台北辦公室"
                    else:
                        upload_df["location"] = upload_df["location"].fillna("台北辦公室")
                    
                    # 轉為字典紀錄清單
                    records_to_insert = []
                    for _, row in upload_df.iterrows():
                        rec = {}
                        for key in ["asset_tag", "name", "asset_type", "category", "serial_number", "status", "holder_name", "holder_department", "location", "cost", "notes"]:
                            if key in upload_df.columns:
                                val = row[key]
                                if pd.isna(val):
                                    rec[key] = None
                                else:
                                    rec[key] = float(val) if key == "cost" else str(val).strip()
                        records_to_insert.append(rec)
                    
                    # 執行 Supabase 批量插入 (UPSERT 覆蓋或新增)
                    res = supabase.table("assets").upsert(records_to_insert, on_conflict="asset_tag").execute()
                    st.success(f"🎉 成功匯入/更新 {len(records_to_insert)} 筆資產資料！請至「資產清單」查看。")
                    
        except Exception as e:
            st.error(f"匯入處理時發生錯誤：{str(e)}")
