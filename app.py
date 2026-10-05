import streamlit as st
import pandas as pd
from datetime import datetime
from supabase import create_client, Client

st.set_page_config(
    page_title="企業資產管理大資料庫",
    page_icon="🏢",
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

# 狀態定義
STATUS_OPTIONS = ["全部", "使用中", "轉移中", "閒置", "備用", "待報廢"]
RAW_STATUS_OPTIONS = ["使用中", "轉移中", "閒置", "備用", "待報廢"]

# 左側邊欄選單分頁
st.sidebar.title("🏢 資產大資料庫")
menu = st.sidebar.radio(
    "業務分類選單",
    [
        "💼 固定資產",
        "📦 低值品",
        "📱 手機 (樣機/外購機)",
        "🔩 物料管理",
        "🔄 狀態異動與轉移",
        "📥 批次匯入 (Excel/CSV)",
        "📊 統計看板"
    ]
)

# 通用過濾與搜尋小工具函式
def render_filter_and_search(menu_name, placeholder_text="搜尋..."):
    c1, c2 = st.columns([1, 2])
    status_filter = c1.selectbox("狀態篩選", STATUS_OPTIONS, key=f"status_{menu_name}")
    keyword = c2.text_input(f"🔍 搜尋 ({placeholder_text})", key=f"kw_{menu_name}")
    return status_filter, keyword

# 通用取得資產並依關鍵字搜尋
def fetch_and_filter_data(asset_type_list, status_filter, keyword):
    query = supabase.table("assets").select("*")
    if asset_type_list:
        query = query.in_("asset_type", asset_type_list)
    if status_filter != "全部":
        query = query.eq("status", status_filter)
    
    data = query.order("created_at", desc=True).execute().data
    df = pd.DataFrame(data)
    
    if not df.empty and keyword:
        kw = keyword.lower().strip()
        searchable_cols = [c for c in ["asset_tag", "material_desc", "name", "category", "material_code", "pcb_no", "imei_no", "holder_name", "user_id_code", "geo_location", "detailed_location", "notes"] if c in df.columns]
        mask = df[searchable_cols].fillna("").astype(str).apply(lambda row: row.str.lower().str.contains(kw)).any(axis=1)
        df = df[mask]
        
    return df

# 格式化表格 (替換 None 為空字串，避免滿版 None)
def clean_display_df(df, col_map):
    for k in col_map.keys():
        if k not in df.columns:
            df[k] = ""
    sub_df = df[list(col_map.keys())].rename(columns=col_map)
    return sub_df.fillna("").astype(str).replace({"None": "", "nan": ""})

# ========================================================
# 1. 固定資產 (含：直接新增 + 直接刪除)
# ========================================================
if menu == "💼 固定資產":
    st.header("💼 固定資產清單")
    status_filter, keyword = render_filter_and_search("固定資產", "資產編號 / 物料描述 / 使用人 / 工號")
    
    df = fetch_and_filter_data(["固定資產"], status_filter, keyword)
    
    if not df.empty:
        col_map = {
            "asset_tag": "資產編號",
            "material_desc": "物料描述",
            "category": "分類",
            "holder_name": "使用人",
            "user_id_code": "使用人工號",
            "geo_location": "地理位置",
            "detailed_location": "詳細地點",
            "status": "狀態",
            "notes": "備註"
        }
        df["material_desc"] = df["material_desc"].fillna(df.get("name", ""))
        df["geo_location"] = df["geo_location"].fillna(df.get("location", ""))
        
        display_df = clean_display_df(df, col_map)
        st.caption(f"共 {len(display_df)} 筆固定資產")
        st.dataframe(display_df, use_container_width=True, hide_index=True, height=600)
        
        csv = display_df.to_csv(index=False).encode('utf-8-sig')
        st.download_button("📥 匯出固定資產清單 (CSV)", csv, "固定資產清單.csv", "text/csv")
    else:
        st.info("目前尚無固定資產資料。")

    st.divider()
    c_add, c_del = st.columns(2)

    # --- 新增固定資產 ---
    with c_add.expander("➕ 快速新增固定資產", expanded=False):
        with st.form("add_fa_form"):
            fa_tag = st.text_input("資產編號 (必填)")
            fa_desc = st.text_input("物料描述 (必填，如: MacBook Pro 14)")
            fa_cat = st.text_input("分類", value="資訊設備")
            fa_holder = st.text_input("使用人")
            fa_uid = st.text_input("使用人工號")
            fa_geo = st.text_input("地理位置", value="台北辦公室")
            fa_loc = st.text_input("詳細地點 (如: 7F 機房/桌號)")
            fa_status = st.selectbox("狀態", RAW_STATUS_OPTIONS, index=2)
            fa_notes = st.text_area("備註說明")
            
            btn_add_fa = st.form_submit_button("確認新增固定資產")
            if btn_add_fa:
                if not fa_tag or not fa_desc:
                    st.error("資產編號與物料描述為必填項！")
                else:
                    try:
                        supabase.table("assets").insert({
                            "asset_tag": fa_tag.strip(),
                            "name": fa_desc.strip(),
                            "material_desc": fa_desc.strip(),
                            "asset_type": "固定資產",
                            "category": fa_cat.strip() if fa_cat else "資訊設備",
                            "holder_name": fa_holder.strip() if fa_holder else None,
                            "user_id_code": fa_uid.strip() if fa_uid else None,
                            "geo_location": fa_geo.strip(),
                            "detailed_location": fa_loc.strip(),
                            "location": fa_geo.strip(),
                            "status": fa_status,
                            "notes": fa_notes.strip() if fa_notes else None
                        }).execute()
                        st.success(f"🎉 固定資產 [{fa_tag}] 新增成功！請重新整理頁面。")
                        st.rerun()
                    except Exception as e:
                        st.error(f"新增失敗：{str(e)}")

    # --- 刪除固定資產 ---
    with c_del.expander("🗑️ 刪除固定資產", expanded=False):
        all_fa = supabase.table("assets").select("id, asset_tag, material_desc, name").eq("asset_type", "固定資產").execute().data
        if all_fa:
            fa_options = {f"{item.get('asset_tag') or '無編號'} - {item.get('material_desc') or item.get('name')} (ID: {item['id'][:8]}...)": item["id"] for item in all_fa}
            selected_fa_label = st.selectbox("選擇欲刪除之固定資產", list(fa_options.keys()))
            confirm_del_fa = st.checkbox("⚠️️ 我確定要永久刪除此項資產", key="confirm_fa")
            if st.button("確認刪除", key="btn_del_fa"):
                if confirm_del_fa:
                    target_id = fa_options[selected_fa_label]
                    supabase.table("assets").delete().eq("id", target_id).execute()
                    st.success("🗑️ 已成功刪除！")
                    st.rerun()
                else:
                    st.warning("請先勾選確認刪除框！")
        else:
            st.info("尚無資產可刪除。")

# ========================================================
# 2. 低值品 (含：直接新增 + 直接刪除)
# ========================================================
elif menu == "📦 低值品":
    st.header("📦 低值品清單")
    status_filter, keyword = render_filter_and_search("低值品", "資產編號 / 資物料描述 / 使用人 / 工號")
    
    df = fetch_and_filter_data(["低值品"], status_filter, keyword)
    
    if not df.empty:
        col_map = {
            "asset_tag": "資產編號",
            "material_desc": "資物料描述",
            "category": "分類",
            "holder_name": "使用人",
            "user_id_code": "使用人工號",
            "status": "狀態",
            "location": "位置",
            "notes": "備註"
        }
        df["material_desc"] = df["material_desc"].fillna(df.get("name", ""))
        df["location"] = df["location"].fillna(df.get("geo_location", ""))
        
        display_df = clean_display_df(df, col_map)
        st.caption(f"共 {len(display_df)} 筆低值品")
        st.dataframe(display_df, use_container_width=True, hide_index=True, height=600)
        
        csv = display_df.to_csv(index=False).encode('utf-8-sig')
        st.download_button("📥 匯出低值品清單 (CSV)", csv, "低值品清單.csv", "text/csv")
    else:
        st.info("目前尚無低值品資料。")

    st.divider()
    c_add, c_del = st.columns(2)

    # --- 新增低值品 ---
    with c_add.expander("➕ 快速新增低值品", expanded=False):
        with st.form("add_low_val_form"):
            lv_tag = st.text_input("資產編號 (無可留空)")
            lv_desc = st.text_input("資物料描述 (必填，如: 羅技無線滑鼠)")
            lv_cat = st.text_input("分類", value="硬碟/記憶體/周邊")
            lv_holder = st.text_input("使用人")
            lv_uid = st.text_input("使用人工號")
            lv_loc = st.text_input("位置", value="台北辦公室")
            lv_status = st.selectbox("狀態", RAW_STATUS_OPTIONS, index=2)
            lv_notes = st.text_area("備註說明")
            
            btn_add_lv = st.form_submit_button("確認新增低值品")
            if btn_add_lv:
                if not lv_desc:
                    st.error("資物料描述為必填項！")
                else:
                    try:
                        supabase.table("assets").insert({
                            "asset_tag": lv_tag.strip() if lv_tag else None,
                            "name": lv_desc.strip(),
                            "material_desc": lv_desc.strip(),
                            "asset_type": "低值品",
                            "category": lv_cat.strip() if lv_cat else "低值品",
                            "holder_name": lv_holder.strip() if lv_holder else None,
                            "user_id_code": lv_uid.strip() if lv_uid else None,
                            "location": lv_loc.strip(),
                            "geo_location": lv_loc.strip(),
                            "status": lv_status,
                            "notes": lv_notes.strip() if lv_notes else None
                        }).execute()
                        st.success("🎉 低值品新增成功！")
                        st.rerun()
                    except Exception as e:
                        st.error(f"新增失敗：{str(e)}")

    # --- 刪除低值品 ---
    with c_del.expander("🗑️ 刪除低值品", expanded=False):
        all_lv = supabase.table("assets").select("id, asset_tag, material_desc, name").eq("asset_type", "低值品").execute().data
        if all_lv:
            lv_options = {f"{item.get('asset_tag') or '無編號'} - {item.get('material_desc') or item.get('name')} (ID: {item['id'][:8]}...)": item["id"] for item in all_lv}
            selected_lv_label = st.selectbox("選擇欲刪除之低值品", list(lv_options.keys()))
            confirm_del_lv = st.checkbox("⚠️ 我確定要永久刪除此項低值品", key="confirm_lv")
            if st.button("確認刪除", key="btn_del_lv"):
                if confirm_del_lv:
                    target_id = lv_options[selected_lv_label]
                    supabase.table("assets").delete().eq("id", target_id).execute()
                    st.success("🗑️ 已成功刪除！")
                    st.rerun()
                else:
                    st.warning("請先勾選確認刪除框！")
        else:
            st.info("尚無低值品可刪除。")

# ========================================================
# 3. 手機 (樣機/外購機) (含：直接新增 + 直接刪除)
# ========================================================
elif menu == "📱 手機 (樣機/外購機)":
    st.header("📱 手機 (樣機 / 外購機 / 測試機) 清單")
    status_filter, keyword = render_filter_and_search("手機", "PCB / IMEI / 物料描述 / 使用人")
    
    df = fetch_and_filter_data(["手機 (樣機/外購機)", "樣機", "外購機", "手機"], status_filter, keyword)
    
    if not df.empty:
        col_map = {
            "pcb_no": "PCB",
            "material_desc": "物料描述",
            "imei_no": "IMEI",
            "material_code": "物料代碼",
            "holder_name": "使用人",
            "user_id_code": "使用人工號",
            "status": "狀態",
            "notes": "備註"
        }
        df["material_desc"] = df["material_desc"].fillna(df.get("name", ""))
        
        display_df = clean_display_df(df, col_map)
        st.caption(f"共 {len(display_df)} 筆手機設備")
        st.dataframe(display_df, use_container_width=True, hide_index=True, height=600)
        
        csv = display_df.to_csv(index=False).encode('utf-8-sig')
        st.download_button("📥 匯出手機清單 (CSV)", csv, "手機樣機清單.csv", "text/csv")
    else:
        st.info("目前尚無手機樣機/外購機資料。")

    st.divider()
    c_add, c_del = st.columns(2)

    # --- 新增手機 ---
    with c_add.expander("➕ 快速新增手機設備 (樣機/外購機)", expanded=False):
        with st.form("add_phone_form"):
            ph_desc = st.text_input("物料描述 (必填，如: Pixel 8 測試機 / iPhone 15)")
            col_p1, col_p2 = st.columns(2)
            ph_pcb = col_p1.text_input("PCB 號碼")
            ph_imei = col_p2.text_input("IMEI 號碼")
            ph_code = col_p1.text_input("物料代碼")
            ph_holder = col_p2.text_input("使用人")
            ph_uid = col_p1.text_input("使用人工號")
            ph_status = col_p2.selectbox("狀態", RAW_STATUS_OPTIONS, index=2)
            ph_notes = st.text_area("備註說明")
            
            btn_add_ph = st.form_submit_button("確認新增手機設備")
            if btn_add_ph:
                if not ph_desc:
                    st.error("物料描述為必填項！")
                else:
                    try:
                        supabase.table("assets").insert({
                            "name": ph_desc.strip(),
                            "material_desc": ph_desc.strip(),
                            "asset_type": "手機 (樣機/外購機)",
                            "category": "手機",
                            "pcb_no": ph_pcb.strip() if ph_pcb else None,
                            "imei_no": ph_imei.strip() if ph_imei else None,
                            "material_code": ph_code.strip() if ph_code else None,
                            "holder_name": ph_holder.strip() if ph_holder else None,
                            "user_id_code": ph_uid.strip() if ph_uid else None,
                            "status": ph_status,
                            "geo_location": "台北辦公室",
                            "location": "台北辦公室",
                            "notes": ph_notes.strip() if ph_notes else None
                        }).execute()
                        st.success("🎉 手機設備新增成功！")
                        st.rerun()
                    except Exception as e:
                        st.error(f"新增失敗：{str(e)}")

    # --- 刪除手機 ---
    with c_del.expander("🗑️ 刪除手機設備", expanded=False):
        all_ph = supabase.table("assets").select("id, material_desc, pcb_no, imei_no, name").in_("asset_type", ["手機 (樣機/外購機)", "樣機", "外購機", "手機"]).execute().data
        if all_ph:
            ph_options = {f"{item.get('material_desc') or item.get('name')} (IMEI: {item.get('imei_no') or '無'} / PCB: {item.get('pcb_no') or '無'})": item["id"] for item in all_ph}
            selected_ph_label = st.selectbox("選擇欲刪除之手機", list(ph_options.keys()))
            confirm_del_ph = st.checkbox("⚠️ 我確定要永久刪除此手機資料", key="confirm_ph")
            if st.button("確認刪除", key="btn_del_ph"):
                if confirm_del_ph:
                    target_id = ph_options[selected_ph_label]
                    supabase.table("assets").delete().eq("id", target_id).execute()
                    st.success("🗑️ 已成功刪除！")
                    st.rerun()
                else:
                    st.warning("請先勾選確認刪除框！")
        else:
            st.info("尚無手機資料可刪除。")

# ========================================================
# 4. 物料管理
# ========================================================
elif menu == "🔩 物料管理":
    st.header("🔩 物料清單")
    status_filter, keyword = render_filter_and_search("物料", "物料代碼 / PCB / 物料描述 / 使用人")
    
    df = fetch_and_filter_data(["物料", "耗材與物料"], status_filter, keyword)
    
    if not df.empty:
        col_map = {
            "material_code": "物料代碼",
            "pcb_no": "IMEI／PCB",
            "material_desc": "物料描述",
            "holder_name": "使用人",
            "user_id_code": "使用人工號",
            "quantity": "數量",
            "status": "狀態",
            "notes": "備註"
        }
        df["material_desc"] = df["material_desc"].fillna(df.get("name", ""))
        df["pcb_no"] = df["pcb_no"].fillna(df.get("imei_no", ""))
        
        display_df = clean_display_df(df, col_map)
        st.caption(f"共 {len(display_df)} 筆物料項目")
        st.dataframe(display_df, use_container_width=True, hide_index=True, height=600)
        
        csv = display_df.to_csv(index=False).encode('utf-8-sig')
        st.download_button("📥 匯出物料清單 (CSV)", csv, "物料清單.csv", "text/csv")
    else:
        st.info("目前尚無物料資料。")

# ========================================================
# 5. 狀態異動與轉移
# ========================================================
elif menu == "🔄 狀態異動與轉移":
    st.header("資產狀態轉移與使用人變更")
    
    asset_query_input = st.text_input("輸入欲異動之「資產編號」或「IMEI」或「PCB」或「物料代碼」")
    
    if asset_query_input:
        kw = asset_query_input.strip()
        res = supabase.table("assets").select("*").or_(
            f"asset_tag.eq.{kw},imei_no.eq.{kw},pcb_no.eq.{kw},material_code.eq.{kw}"
        ).execute()
        
        if res.data:
            item = res.data[0]
            curr_holder = item.get('holder_name') or '無'
            curr_code = f" ({item.get('user_id_code')})" if item.get('user_id_code') else ""
            st.success(f"找到設備：[{item.get('asset_type')}] {item.get('material_desc') or item.get('name')} | 狀態：【{item['status']}】 | 目前使用人：{curr_holder}{curr_code}")
            
            with st.form("transfer_form"):
                new_status = st.selectbox("變更後狀態", RAW_STATUS_OPTIONS, index=RAW_STATUS_OPTIONS.index(item['status']) if item['status'] in RAW_STATUS_OPTIONS else 0)
                col_u1, col_u2 = st.columns(2)
                new_holder = col_u1.text_input("新使用人姓名", value=item.get("holder_name") or "")
                new_user_id = col_u2.text_input("新使用人工號", value=item.get("user_id_code") or "")
                
                col_l1, col_l2 = st.columns(2)
                new_geo = col_l1.text_input("地理位置", value=item.get("geo_location") or item.get("location") or "台北辦公室")
                new_detail_loc = col_l2.text_input("詳細地點", value=item.get("detailed_location") or "")
                
                transfer_remark = st.text_area("本次異動備註 (如: 移交新進人員、外借測試、歸還庫存)")
                operator = st.text_input("經辦人姓名", value="Admin")
                
                btn_transfer = st.form_submit_button("確認提交更新")
                if btn_transfer:
                    supabase.table("assets").update({
                        "status": new_status,
                        "holder_name": new_holder.strip() if new_holder else None,
                        "user_id_code": new_user_id.strip() if new_user_id else None,
                        "geo_location": new_geo.strip(),
                        "detailed_location": new_detail_loc.strip(),
                        "location": new_geo.strip(),
                        "updated_at": datetime.utcnow().isoformat()
                    }).eq("id", item["id"]).execute()
                    
                    supabase.table("asset_logs").insert({
                        "asset_id": item["id"],
                        "asset_tag": item.get("asset_tag") or item.get("material_code") or item.get("imei_no") or "N/A",
                        "action_type": f"變更狀態為-{new_status}",
                        "previous_holder": item.get("holder_name"),
                        "new_holder": new_holder,
                        "operator": operator,
                        "remark": f"[工號: {new_user_id}] {transfer_remark}"
                    }).execute()
                    
                    st.success("✅ 狀態與使用人已同步更新至 Supabase！")
        else:
            st.error("查無此編號/IMEI/PCB/物料代碼，請重新確認。")

# ========================================================
# 6. 批次匯入
# ========================================================
elif menu == "📥 批次匯入 (Excel/CSV)":
    st.header("資產資料批次匯入")
    st.write("直接上傳既有的 Excel 或 CSV 表格，系統會自動去除多餘空格並辨識欄位。")
    
    uploaded_file = st.file_uploader("上傳 Excel 或 CSV 檔案", type=["csv", "xlsx"])
    
    if uploaded_file is not None:
        try:
            if uploaded_file.name.endswith(".csv"):
                df_up = pd.read_csv(uploaded_file)
            else:
                df_up = pd.read_excel(uploaded_file)
                
            df_up.columns = [str(c).strip() for c in df_up.columns]
            
            st.write("預覽匯入資料（前 5 筆）：")
            st.dataframe(df_up.head(), use_container_width=True)
            
            col_map = {
                "資產主類型": "asset_type", "資產類型": "asset_type", "類型": "asset_type",
                "資產編號": "asset_tag", "設備編號": "asset_tag", "編號": "asset_tag", "asset_tag": "asset_tag",
                "物料描述": "material_desc", "資物料描述": "material_desc", "設備名稱": "material_desc", "品名": "material_desc", "規格": "material_desc",
                "物料代碼": "material_code", "料號": "material_code",
                "分類": "category", "類別": "category",
                "PCB": "pcb_no", "PCB號碼": "pcb_no", "PCB NO": "pcb_no",
                "IMEI": "imei_no", "IMEI號碼": "imei_no", "IMEI／PCB": "pcb_no", "IMEI/PCB": "pcb_no",
                "使用人": "holder_name", "保管人": "holder_name", "借用人": "holder_name", "姓名": "holder_name",
                "使用人工號": "user_id_code", "工號": "user_id_code", "員工編號": "user_id_code", "員編": "user_id_code",
                "狀態": "status",
                "地理位置": "geo_location", "位置": "location", "存放地點": "geo_location",
                "詳細地點": "detailed_location", "詳細位置": "detailed_location",
                "數量": "quantity",
                "備註": "notes"
            }
            
            target_asset_type = st.selectbox(
                "若上傳表格未註明「資產主類型」，預設歸類為：",
                ["低值品", "固定資產", "手機 (樣機/外購機)", "物料"]
            )
            
            if st.button("🚀 確認將資料整批匯入 Supabase"):
                df_up = df_up.rename(columns=col_map)
                records = []
                for _, row in df_up.iterrows():
                    rec = {}
                    desc = str(row.get("material_desc") or "").strip()
                    rec["material_desc"] = desc if desc and desc.lower() != "nan" else None
                    rec["name"] = desc if desc and desc.lower() != "nan" else "未命名項目"
                    
                    st_val = str(row.get("status") or "").strip()
                    if st_val in ["在用中", "使用中"]:
                        rec["status"] = "使用中"
                    elif st_val in ["轉移中", "備用", "待報廢"]:
                        rec["status"] = st_val
                    else:
                        rec["status"] = "閒置"
                        
                    atype = row.get("asset_type")
                    if pd.notna(atype) and str(atype).strip() and str(atype).strip().lower() != "nan":
                        atype_str = str(atype).strip()
                        if atype_str in ["樣機", "外購機"]:
                            rec["asset_type"] = "手機 (樣機/外購機)"
                        else:
                            rec["asset_type"] = atype_str
                    else:
                        rec["asset_type"] = target_asset_type
                        
                    rec["quantity"] = int(row.get("quantity")) if pd.notna(row.get("quantity")) and str(row.get("quantity")).isdigit() else 1
                    
                    tag_v = row.get("asset_tag")
                    rec["asset_tag"] = str(tag_v).strip() if pd.notna(tag_v) and str(tag_v).strip().lower() != "nan" else None
                    
                    for k in ["material_code", "category", "pcb_no", "imei_no", "holder_name", "user_id_code", "geo_location", "detailed_location", "location", "notes"]:
                        val = row.get(k)
                        rec[k] = str(val).strip() if pd.notna(val) and str(val).strip().lower() != "nan" else None
                    
                    if not rec.get("location"):
                        rec["location"] = rec.get("geo_location") or "台北辦公室"
                    records.append(rec)
                
                supabase.table("assets").insert(records).execute()
                st.success(f"🎉 成功匯入 {len(records)} 筆資料至【{target_asset_type}】！")
                
        except Exception as e:
            st.error(f"匯入錯誤：{str(e)}")

# ========================================================
# 7. 統計看板
# ========================================================
elif menu == "📊 統計看板":
    st.header("全公司資產分佈概況")
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
        g1, g2 = st.columns(2)
        with g1:
            st.subheader("各大業務分類數量")
            st.bar_chart(df["asset_type"].fillna("未分類").value_counts())
        with g2:
            st.subheader("整體狀態分佈")
            st.bar_chart(df["status"].value_counts())
    else:
        st.info("尚無統計數據。")
