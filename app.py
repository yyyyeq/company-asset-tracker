import streamlit as st
import pandas as pd
from datetime import datetime
from supabase import create_client, Client

st.set_page_config(
    page_title="企業資產管理大資料庫",
    page_icon="🏢",
    layout="wide"
)

# 1. 取得 Supabase 連線
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

# 狀態定義
STATUS_OPTIONS = ["全部", "使用中", "轉移中", "閒置", "備用", "待報廢"]
RAW_STATUS_OPTIONS = ["使用中", "轉移中", "閒置", "備用", "待報廢"]

# 資產分類定義
MAIN_CATEGORIES = ["全部", "固定資產", "低值品", "物料", "手機 (樣機/外購機)"]

# 各分類顯示欄位映射
VIEW_COLUMN_MAP = {
    "低值品": {
        "asset_tag": "資產編號",
        "material_desc": "資物料描述",
        "category": "分類",
        "holder_name": "使用人",
        "user_id_code": "使用人工號",
        "status": "狀態",
        "location": "位置",
        "notes": "備註"
    },
    "固定資產": {
        "asset_tag": "資產編號",
        "material_desc": "物料描述",
        "category": "分類",
        "holder_name": "使用人",
        "user_id_code": "使用人工號",
        "geo_location": "地理位置",
        "detailed_location": "詳細地點",
        "status": "狀態",
        "notes": "備註"
    },
    "手機 (樣機/外購機)": {
        "pcb_no": "PCB",
        "material_desc": "物料描述",
        "imei_no": "IMEI",
        "material_code": "物料代碼",
        "holder_name": "使用人",
        "user_id_code": "使用人工號",
        "status": "狀態",
        "notes": "備註"
    },
    "物料": {
        "material_code": "物料代碼",
        "pcb_no": "IMEI／PCB",
        "material_desc": "物料描述",
        "holder_name": "使用人",
        "user_id_code": "使用人工號",
        "quantity": "數量",
        "status": "狀態",
        "notes": "備註"
    }
}

# 側邊欄導航
st.sidebar.title("🏢 資產大資料庫")
menu = st.sidebar.radio(
    "導航選單",
    ["📋 資產清單與各類別視圖", "🔄 狀態異動與轉移", "➕ 單筆資料建檔", "📥 Excel/CSV 批次匯入", "📊 數據看板"]
)

# ----------------- 模組 1: 資產清單與查詢 (專屬客製欄位) -----------------
if menu == "📋 資產清單與查詢 (各類別視圖)":
    st.header("資產大資料庫檢索")
    
    col_c1, col_c2, col_c3 = st.columns([1.5, 1, 2])
    selected_main_cat = col_c1.selectbox("選擇資產主類型", MAIN_CATEGORIES)
    selected_status = col_c2.selectbox("篩選狀態", STATUS_OPTIONS)
    search_keyword = col_c3.text_input("🔍 關鍵字搜尋 (編號/IMEI/PCB/物料描述/使用人/工號)")

    query = supabase.table("assets").select("*")
    
    # 類型過濾
    if selected_main_cat != "全部":
        if selected_main_cat == "手機 (樣機/外購機)":
            query = query.in_("asset_type", ["樣機", "外購機", "手機 (樣機/外購機)"])
        else:
            query = query.eq("asset_type", selected_main_cat)
            
    # 狀態過濾
    if selected_status != "全部":
        query = query.eq("status", selected_status)
        
    data = query.order("created_at", desc=True).execute().data
    df = pd.DataFrame(data)

    if not df.empty:
        # 關鍵字篩選
        if search_keyword:
            kw = search_keyword.lower()
            df = df[
                df["asset_tag"].fillna("").astype(str).str.lower().str.contains(kw) |
                df["material_desc"].fillna("").astype(str).str.lower().str.contains(kw) |
                df["material_code"].fillna("").astype(str).str.lower().str.contains(kw) |
                df["imei_no"].fillna("").astype(str).str.lower().str.contains(kw) |
                df["pcb_no"].fillna("").astype(str).str.lower().str.contains(kw) |
                df["holder_name"].fillna("").astype(str).str.lower().str.contains(kw) |
                df["user_id_code"].fillna("").astype(str).str.lower().str.contains(kw)
            ]

        # 根據所選類型動態調整欄位名稱與順序
        if selected_main_cat in VIEW_COLUMN_MAP:
            target_map = VIEW_COLUMN_MAP[selected_main_cat]
            cols = [k for k in target_map.keys() if k in df.columns]
            display_df = df[cols].rename(columns=target_map)
        else:
            # 綜合全覽視圖
            all_cols = {
                "asset_tag": "資產編號", "asset_type": "類型", "category": "分類",
                "material_desc": "物料描述", "material_code": "物料代碼", "pcb_no": "PCB", "imei_no": "IMEI",
                "holder_name": "使用人", "user_id_code": "使用人工號", "status": "狀態",
                "geo_location": "地理位置", "detailed_location": "詳細地點", "quantity": "數量", "notes": "備註"
            }
            cols = [k for k in all_cols.keys() if k in df.columns]
            display_df = df[cols].rename(columns=all_cols)

        st.caption(f"共找到 {len(display_df)} 筆紀錄")
        st.dataframe(display_df, use_container_width=True, hide_index=True)

        # 匯出 CSV
        csv = display_df.to_csv(index=False).encode('utf-8-sig')
        st.download_button(f"📥 匯出 {selected_main_cat} 清單 (CSV)", csv, f"{selected_main_cat}_清單.csv", "text/csv")
    else:
        st.info("查無符合條件的資產資料。")

# ----------------- 模組 2: 狀態異動與轉移 -----------------
elif menu == "🔄 狀態異動與轉移":
    st.header("資產狀態轉移與使用人變更")
    
    asset_query_input = st.text_input("輸入欲異動之「資產編號」或「IMEI」或「PCB」")
    
    if asset_query_input:
        res = supabase.table("assets").select("*").or_(
            f"asset_tag.eq.{asset_query_input.strip()},imei_no.eq.{asset_query_input.strip()},pcb_no.eq.{asset_query_input.strip()}"
        ).execute()
        
        if res.data:
            item = res.data[0]
            st.success(f"找到資產：[{item.get('asset_type')}] {item.get('material_desc') or item.get('name')} | 目前狀態：【{item['status']}】 | 目前使用人：{item.get('holder_name') or '無'} ({item.get('user_id_code') or '無工號'})")
            
            with st.form("transfer_form"):
                new_status = st.selectbox("變更後狀態", RAW_STATUS_OPTIONS, index=RAW_STATUS_OPTIONS.index(item['status']) if item['status'] in RAW_STATUS_OPTIONS else 0)
                col_u1, col_u2 = st.columns(2)
                new_holder = col_u1.text_input("新使用人姓名", value=item.get("holder_name") or "")
                new_user_id = col_u2.text_input("新使用人工號", value=item.get("user_id_code") or "")
                
                col_l1, col_l2 = st.columns(2)
                new_geo = col_l1.text_input("地理位置 (如: 台北辦公室)", value=item.get("geo_location") or item.get("location") or "")
                new_detail_loc = col_l2.text_input("詳細地點 (如: 機房櫃位/桌號)", value=item.get("detailed_location") or "")
                
                transfer_remark = st.text_area("本次異動備註 (如: 跨組調撥、借出測試、退回庫房)")
                operator = st.text_input("經辦人員", value="Admin")
                
                btn_transfer = st.form_submit_button("確認提交更新")
                if btn_transfer:
                    # 更新主表
                    supabase.table("assets").update({
                        "status": new_status,
                        "holder_name": new_holder.strip() if new_holder else None,
                        "user_id_code": new_user_id.strip() if new_user_id else None,
                        "geo_location": new_geo.strip(),
                        "detailed_location": new_detail_loc.strip(),
                        "updated_at": datetime.utcnow().isoformat()
                    }).eq("id", item["id"]).execute()
                    
                    # 寫入稽核紀錄
                    supabase.table("asset_logs").insert({
                        "asset_id": item["id"],
                        "asset_tag": item.get("asset_tag") or item.get("material_code") or "N/A",
                        "action_type": f"變更為-{new_status}",
                        "previous_holder": item.get("holder_name"),
                        "new_holder": new_holder,
                        "operator": operator,
                        "remark": f"[工號: {new_user_id}] {transfer_remark}"
                    }).execute()
                    
                    st.success("✅ 狀態與使用人已同步更新至 Supabase！")
        else:
            st.error("查無此編號/IMEI/PCB，請重新確認。")

# ----------------- 模組 3: 單筆資料建檔 -----------------
elif menu == "➕ 單筆資料建檔":
    st.header("建立新資產資料")
    
    asset_type = st.selectbox("欲新增的資產類型", ["固定資產", "低值品", "手機 (樣機/外購機)", "物料"])
    
    with st.form("new_single_asset"):
        col1, col2 = st.columns(2)
        
        # 根據選擇的類型呈現專屬欄位
        if asset_type == "低值品":
            tag = col1.text_input("資產編號 (必填)")
            material_desc = col2.text_input("資物料描述 (必填)")
            category = col1.text_input("分類 (如: 周邊配件、文具耗材)", value="低值品")
            location = col2.text_input("位置", value="台北辦公室")
            holder = col1.text_input("使用人")
            user_id = col2.text_input("使用人工號")
            status = col1.selectbox("狀態", RAW_STATUS_OPTIONS, index=2) # 預設閒置
            pcb_no, imei_no, mat_code, geo_loc, detail_loc, qty = None, None, None, location, "", 1

        elif asset_type == "固定資產":
            tag = col1.text_input("資產編號 (必填)")
            material_desc = col2.text_input("物料描述 (如: MacBook Pro 14)")
            category = col1.text_input("分類", value="資訊設備")
            geo_loc = col2.text_input("地理位置", value="台北辦公室")
            detail_loc = col1.text_input("詳細地點 (如: 7F 機房 A 架)")
            holder = col2.text_input("使用人")
            user_id = col1.text_input("使用人工號")
            status = col2.selectbox("狀態", RAW_STATUS_OPTIONS, index=2)
            pcb_no, imei_no, mat_code, location, qty = None, None, None, geo_loc, 1

        elif asset_type == "手機 (樣機/外購機)":
            mat_code = col1.text_input("物料代碼")
            material_desc = col2.text_input("物料描述 (如: Pixel 8 測試機)")
            pcb_no = col1.text_input("PCB 號碼")
            imei_no = col2.text_input("IMEI 號碼")
            holder = col1.text_input("使用人")
            user_id = col2.text_input("使用人工號")
            status = col1.selectbox("狀態", RAW_STATUS_OPTIONS, index=2)
            tag = imei_no or pcb_no or mat_code
            category, geo_loc, detail_loc, location, qty = "手機", "台北辦公室", "", "台北辦公室", 1

        else: # 物料
            mat_code = col1.text_input("物料代碼 (必填)")
            pcb_no = col2.text_input("IMEI／PCB 號碼")
            material_desc = col1.text_input("物料描述 (必填)")
            qty = col2.number_input("數量", min_value=1, value=1)
            holder = col1.text_input("使用人")
            user_id = col2.text_input("使用人工號")
            status = col1.selectbox("狀態", RAW_STATUS_OPTIONS, index=2)
            tag = mat_code
            category, imei_no, geo_loc, detail_loc, location = "物料", pcb_no, "台北辦公室", "", "台北辦公室"

        notes = st.text_area("備註說明")
        
        btn_submit = st.form_submit_button("儲存至資料庫")
        if btn_submit:
            if not material_desc:
                st.error("物料描述為必填項目！")
            else:
                try:
                    payload = {
                        "asset_tag": tag.strip() if tag else None,
                        "name": material_desc.strip(),
                        "asset_type": asset_type,
                        "category": category,
                        "material_desc": material_desc.strip(),
                        "material_code": mat_code.strip() if mat_code else None,
                        "pcb_no": pcb_no.strip() if pcb_no else None,
                        "imei_no": imei_no.strip() if imei_no else None,
                        "status": status,
                        "holder_name": holder.strip() if holder else None,
                        "user_id_code": user_id.strip() if user_id else None,
                        "location": location,
                        "geo_location": geo_loc,
                        "detailed_location": detail_loc,
                        "quantity": int(qty),
                        "notes": notes
                    }
                    res = supabase.table("assets").insert(payload).execute()
                    st.success(f"🎉 [{asset_type}] 資料建立成功！")
                except Exception as e:
                    st.error(f"新增失敗：{str(e)}")

# ----------------- 模組 4: 批次匯入 (Excel/CSV) -----------------
elif menu == "📥 Excel/CSV 批次匯入":
    st.header("資產資料批次匯入")
    st.write("直接匯入公司現有的 Excel 或 CSV 表格，系統會依欄位名稱自動轉換對齊。")
    
    # 標準範本下載
    sample_data = pd.DataFrame([{
        "資產主類型": "固定資產",
        "資產編號": "FA-2026-001",
        "物料描述": "Dell 27吋 4K 螢幕",
        "物料代碼": "MAT-001",
        "分類": "螢幕設備",
        "PCB": "",
        "IMEI": "",
        "使用人": "王小明",
        "使用人工號": "EMP0123",
        "狀態": "使用中",
        "地理位置": "台北辦公室",
        "詳細地點": "7F 開放辦公區-桌號12",
        "數量": 1,
        "備註": "雙螢幕配置之一"
    }, {
        "資產主類型": "手機 (樣機/外購機)",
        "資產編號": "MP-2026-099",
        "物料描述": "測試用 Pixel 8",
        "物料代碼": "MAT-002",
        "分類": "測試手機",
        "PCB": "PCB-987654",
        "IMEI": "358912345678901",
        "使用人": "李大華",
        "使用人工號": "EMP0456",
        "狀態": "使用中",
        "地理位置": "台北辦公室",
        "詳細地點": "實驗室樣品櫃",
        "數量": 1,
        "備註": "出差借測中"
    }])
    
    sample_csv = sample_data.to_csv(index=False).encode('utf-8-sig')
    st.download_button("📄 下載標準匯入範本 (CSV)", sample_csv, "企業資產統一匯入範本.csv", "text/csv")
    
    st.divider()
    uploaded_file = st.file_uploader("上傳 Excel 或 CSV 檔案", type=["csv", "xlsx"])
    
    if uploaded_file is not None:
        try:
            if uploaded_file.name.endswith(".csv"):
                df_up = pd.read_csv(uploaded_file)
            else:
                df_up = pd.read_excel(uploaded_file)
                
            st.write("預覽匯入資料（前 5 筆）：")
            st.dataframe(df_up.head(), use_container_width=True)
            
            # 欄位映射轉換
            col_map = {
                "資產主類型": "asset_type",
                "資產編號": "asset_tag",
                "物料描述": "material_desc",
                "資物料描述": "material_desc",
                "設備名稱": "material_desc",
                "物料代碼": "material_code",
                "分類": "category",
                "PCB": "pcb_no",
                "PCB號碼": "pcb_no",
                "IMEI": "imei_no",
                "IMEI／PCB": "pcb_no",
                "使用人": "holder_name",
                "使用人工號": "user_id_code",
                "狀態": "status",
                "地理位置": "geo_location",
                "位置": "geo_location",
                "詳細地點": "detailed_location",
                "數量": "quantity",
                "備註": "notes"
            }
            
            if st.button("🚀 確認將資料整批匯入 Supabase"):
                df_up = df_up.rename(columns=col_map)
                
                records = []
                for _, row in df_up.iterrows():
                    rec = {}
                    # 補 name 預設
                    rec["name"] = str(row.get("material_desc") or row.get("asset_tag") or "未命名設備")
                    rec["status"] = str(row.get("status") or "閒置")
                    rec["asset_type"] = str(row.get("asset_type") or "固定資產")
                    rec["quantity"] = int(row.get("quantity")) if pd.notna(row.get("quantity")) else 1
                    
                    for k in ["asset_tag", "material_desc", "material_code", "category", "pcb_no", "imei_no", "holder_name", "user_id_code", "geo_location", "detailed_location", "notes"]:
                        val = row.get(k)
                        rec[k] = str(val).strip() if pd.notna(val) else None
                    records.append(rec)
                
                # 批量插入
                supabase.table("assets").insert(records).execute()
                st.success(f"🎉 成功匯入 {len(records)} 筆資產資料！請至清單查看。")
                
        except Exception as e:
            st.error(f"匯入錯誤：{str(e)}")

# ----------------- 模組 5: 數據看板 -----------------
elif menu == "📊 數據看板":
    st.header("庫存與狀態統計概況")
    res = supabase.table("assets").select("*").execute()
    df = pd.DataFrame(res.data)
    
    if not df.empty:
        c1, c2, c3, c4, c5 = st.columns(5)
        c1.metric("使用中", len(df[df["status"] == "使用中"]))
        c2.metric("轉移中", len(df[df["status"] == "轉移中"]))
        c3.metric("閒置", len(df[df["status"] == "閒置"]))
        c4.metric("備用", len(df[df["status"] == "備用"]))
        c5.metric("待報廢", len(df[df["status"] == "待報廢"]))
        
        st.divider()
        col_g1, col_g2 = st.columns(2)
        with col_g1:
            st.subheader("資產主類型分佈")
            st.bar_chart(df["asset_type"].fillna("未分類").value_counts())
        with col_g2:
            st.subheader("五大狀態分佈")
            st.bar_chart(df["status"].value_counts())
    else:
        st.info("尚無資料。")
