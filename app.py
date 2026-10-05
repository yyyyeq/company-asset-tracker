import streamlit as st
import pandas as pd
from datetime import datetime
from supabase import create_client, Client

st.set_page_config(
    page_title="資產管理平台",
    page_icon="💻",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 注入現代化企業風格 CSS
st.markdown("""
<style>
    /* 全域字體與背景優化 */
    html, body, [class*="css"] {
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
    }
    
    /* KPI 統計卡片 */
    .metric-card {
        background-color: #ffffff;
        border: 1px solid #e2e8f0;
        border-radius: 12px;
        padding: 16px 20px;
        box-shadow: 0 1px 3px rgba(0,0,0,0.05);
        display: flex;
        flex-direction: column;
        justify-content: center;
    }
    .metric-label {
        font-size: 0.85rem;
        color: #64748b;
        font-weight: 500;
        margin-bottom: 4px;
    }
    .metric-value {
        font-size: 1.6rem;
        font-weight: 700;
        color: #0f172a;
    }
    
    /* 側邊欄美化 */
    [data-testid="stSidebar"] {
        background-color: #f8fafc;
        border-right: 1px solid #e2e8f0;
    }
    
    /* 按鈕圓角與陰影 */
    .stButton>button {
        border-radius: 8px;
        font-weight: 500;
        transition: all 0.15s ease;
    }
    .stButton>button:hover {
        transform: translateY(-1px);
        box-shadow: 0 4px 6px -1px rgba(0,0,0,0.1);
    }
    
    /* Expander 收合框美化 */
    .streamlit-expanderHeader {
        background-color: #f1f5f9;
        border-radius: 8px;
        font-weight: 600;
    }
</style>
""", unsafe_allow_html=True)

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

# 選項定義
STATUS_OPTIONS = ["全部", "使用中", "轉移中", "閒置", "備用", "待報廢"]
RAW_STATUS_OPTIONS = ["使用中", "轉移中", "閒置", "備用", "待報廢"]
WAREHOUSE_OPTIONS = ["全部", "個人倉", "部門倉"]
RAW_WAREHOUSE_OPTIONS = ["個人倉", "部門倉"]

# 安全分批刪除函式
def safe_batch_delete(supabase_client, id_list, chunk_size=20):
    for i in range(0, len(id_list), chunk_size):
        chunk = id_list[i:i + chunk_size]
        supabase_client.table("assets").delete().in_("id", chunk).execute()

# 左側邊欄選單分頁
st.sidebar.markdown("### 🏢 資產管理平台")
st.sidebar.caption("Asset Tracking System")
menu = st.sidebar.radio(
    "模組選單",
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

# 動態抓取「同仁姓名與工號對照表」
def get_employee_directory():
    res = supabase.table("assets").select("holder_name, user_id_code").execute()
    data = res.data or []
    if not data:
        return pd.DataFrame(columns=["姓名", "工號", "持有設備總數"])
    
    df_emp = pd.DataFrame(data)
    df_emp = df_emp[df_emp["holder_name"].notna() & (df_emp["holder_name"].str.strip() != "") & (df_emp["holder_name"] != "None")]
    if df_emp.empty:
        return pd.DataFrame(columns=["姓名", "工號", "持有設備總數"])
    
    df_emp["holder_name"] = df_emp["holder_name"].astype(str).str.strip()
    df_emp["user_id_code"] = df_emp["user_id_code"].fillna("").astype(str).str.strip().replace({"None": "", "nan": ""})
    
    summary = df_emp.groupby(["holder_name", "user_id_code"]).size().reset_index(name="持有設備總數")
    summary = summary.rename(columns={"holder_name": "姓名", "user_id_code": "工號"})
    return summary

# 頂部精美指標卡 (KPI Cards)
def render_metric_header(df):
    total = len(df)
    in_use = len(df[df["status"] == "使用中"])
    idle = len(df[df["status"].isin(["閒置", "備用"])])
    dept_wh = len(df[df["warehouse_type"] == "部門倉"]) if "warehouse_type" in df.columns else 0
    
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.markdown(f'<div class="metric-card"><div class="metric-label">總數量</div><div class="metric-value">{total} <span style="font-size:0.9rem;font-weight:400;color:#94a3b8">件</span></div></div>', unsafe_allow_html=True)
    with c2:
        st.markdown(f'<div class="metric-card"><div class="metric-label">使用中</div><div class="metric-value" style="color:#16a34a">{in_use} <span style="font-size:0.9rem;font-weight:400;color:#94a3b8">件</span></div></div>', unsafe_allow_html=True)
    with c3:
        st.markdown(f'<div class="metric-card"><div class="metric-label">庫存閒置/備用</div><div class="metric-value" style="color:#2563eb">{idle} <span style="font-size:0.9rem;font-weight:400;color:#94a3b8">件</span></div></div>', unsafe_allow_html=True)
    with c4:
        st.markdown(f'<div class="metric-card"><div class="metric-label">部門公用倉</div><div class="metric-value" style="color:#7c3aed">{dept_wh} <span style="font-size:0.9rem;font-weight:400;color:#94a3b8">件</span></div></div>', unsafe_allow_html=True)
    st.write("")

# 狀態視覺化標籤
def format_status_badge(status):
    if status == "使用中":
        return "🟢 使用中"
    elif status == "轉移中":
        return "🟡 轉移中"
    elif status in ["閒置", "備用"]:
        return "🔵 " + str(status)
    elif status == "待報廢":
        return "🔴 待報廢"
    return str(status)

# 搜尋列與速查表 (含動態分類快篩)
def render_filter_and_search(menu_name, available_categories, placeholder_text="搜尋..."):
    with st.expander("👥 姓名與工號速查名冊", expanded=False):
        emp_df = get_employee_directory()
        if not emp_df.empty:
            q_col, sort_col, order_col = st.columns([2, 1, 1])
            emp_search = q_col.text_input("🔍 關鍵字過濾", key=f"emp_search_{menu_name}", placeholder="輸入姓名或工號...")
            sort_by = sort_col.selectbox("排序依據", ["工號", "姓名", "持有設備總數"], key=f"emp_sort_{menu_name}")
            sort_order = order_col.selectbox("順序", ["由小到大 (遞增)", "由大到小 (遞減)"], key=f"emp_order_{menu_name}")
            
            filtered_emp = emp_df.copy()
            if emp_search:
                s = emp_search.strip().lower()
                filtered_emp = filtered_emp[
                    filtered_emp["同仁姓名"].str.lower().str.contains(s) | 
                    filtered_emp["工號"].str.lower().str.contains(s)
                ]
            
            is_ascending = (sort_order == "由小到大 (遞增)")
            filtered_emp = filtered_emp.sort_values(by=sort_by, ascending=is_ascending).reset_index(drop=True)
            st.caption(f"共 {len(filtered_emp)} 位（依【{sort_by}】{sort_order}）")
            st.dataframe(filtered_emp, use_container_width=True, hide_index=True, height=180)
        else:
            st.caption("目前尚無人員資料。")

    # 4 欄複合式快篩（狀態、庫別、設備分類、關鍵字）
    c1, c2, c3, c4 = st.columns([1, 1, 1.2, 1.8])
    status_filter = c1.selectbox("狀態篩選", STATUS_OPTIONS, key=f"status_{menu_name}")
    wh_filter = c2.selectbox("庫別篩選", WAREHOUSE_OPTIONS, key=f"wh_{menu_name}")
    
    cat_options = ["全部"] + list(available_categories.keys())
    cat_selection = c3.selectbox("設備分類", cat_options, key=f"cat_{menu_name}")
    actual_cat_filter = available_categories.get(cat_selection, "全部")
    
    keyword = c4.text_input(f"🔍 搜尋資產 ({placeholder_text})", key=f"kw_{menu_name}")
    return status_filter, wh_filter, actual_cat_filter, keyword

# 資料擷取與過濾
def fetch_and_filter_data(asset_type_list, status_filter, wh_filter, cat_filter, keyword):
    query = supabase.table("assets").select("*")
    if asset_type_list:
        query = query.in_("asset_type", asset_type_list)
    if status_filter != "全部":
        query = query.eq("status", status_filter)
    if wh_filter != "全部":
        query = query.eq("warehouse_type", wh_filter)
    if cat_filter != "全部":
        query = query.eq("category", cat_filter)
    
    data = query.order("created_at", desc=True).execute().data
    df = pd.DataFrame(data)
    
    if not df.empty and keyword:
        kw = keyword.lower().strip()
        searchable_cols = [c for c in ["asset_tag", "material_desc", "name", "category", "material_code", "pcb_no", "imei_no", "holder_name", "user_id_code", "geo_location", "detailed_location", "notes", "warehouse_type"] if c in df.columns]
        mask = df[searchable_cols].fillna("").astype(str).apply(lambda row: row.str.lower().str.contains(kw)).any(axis=1)
        df = df[mask]
        
    return df

# 格式化表格輸出
def clean_display_df(df, col_map):
    for k in col_map.keys():
        if k not in df.columns:
            df[k] = ""
    cols_to_extract = ["id"] + list(col_map.keys())
    sub_df = df[cols_to_extract].copy()
    sub_df = sub_df.rename(columns=col_map)
    for c in sub_df.columns:
        if c != "id":
            sub_df[c] = sub_df[c].fillna("").astype(str).replace({"None": "", "nan": ""})
    return sub_df

# 取得特定資產類型的所有分類選項（附數量）
def get_category_counts(asset_types):
    res = supabase.table("assets").select("category").in_("asset_type", asset_types).execute().data
    if not res:
        return {}
    s = pd.Series([r.get("category") for r in res if r.get("category")]).value_counts()
    return {f"{k} ({v})": k for k, v in s.items()}

# 產生智慧匯出檔名
def generate_export_filename(prefix, wh, status):
    date_str = datetime.now().strftime("%Y%m%d")
    wh_str = f"_{wh}" if wh != "全部" else ""
    st_str = f"_{status}" if status != "全部" else ""
    return f"{prefix}{wh_str}{st_str}_{date_str}.csv"

# ========================================================
# 1. 固定資產
# ========================================================
if menu == "💼 固定資產":
    st.header("💼 固定資產管理")
    
    raw_df = supabase.table("assets").select("*").eq("asset_type", "固定資產").execute().data
    if raw_df:
        render_metric_header(pd.DataFrame(raw_df))
    
    fa_cats = get_category_counts(["固定資產"])
    status_filter, wh_filter, cat_filter, keyword = render_filter_and_search("固定資產", fa_cats, "資產編號 / 物料描述 / 使用人 / 工號")
    df = fetch_and_filter_data(["固定資產"], status_filter, wh_filter, cat_filter, keyword)
    
    if not df.empty:
        col_map = {
            "asset_tag": "資產編號",
            "material_desc": "物料描述",
            "warehouse_type": "庫別",
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
        df["warehouse_type"] = df["warehouse_type"].fillna("個人倉")
        df["status"] = df["status"].apply(format_status_badge)
        display_df = clean_display_df(df, col_map)
        
        c_sel_all, c_info = st.columns([1.2, 3.8])
        select_all_fa = c_sel_all.checkbox("🔘 全選此畫面資料", key="select_all_fa")
        c_info.caption(f"顯示共 {len(display_df)} 筆固定資產")
        
        display_df.insert(0, "選取", select_all_fa)
        
        # 黃金比例排版
        edited_df = st.data_editor(
            display_df,
            hide_index=True,
            use_container_width=True,
            height=600,
            key="editor_fa",
            column_config={
                "id": None,
                "選取": st.column_config.CheckboxColumn("選取", width="small", default=select_all_fa),
                "資產編號": st.column_config.TextColumn("資產編號", width="medium"),
                "物料描述": st.column_config.TextColumn("物料描述", width="large"),
                "庫別": st.column_config.TextColumn("庫別", width="small"),
                "分類": st.column_config.TextColumn("分類", width="small"),
                "使用人": st.column_config.TextColumn("使用人", width="small"),
                "使用人工號": st.column_config.TextColumn("使用人工號", width="small"),
                "地理位置": st.column_config.TextColumn("地理位置", width="small"),
                "詳細地點": st.column_config.TextColumn("詳細地點", width="medium"),
                "狀態": st.column_config.TextColumn("狀態", width="small"),
                "備註": st.column_config.TextColumn("備註", width="medium")
            },
            disabled=[c for c in display_df.columns if c != "選取"]
        )
        
        selected_rows = edited_df[edited_df["選取"] == True]
        c_del_batch, c_clear_all, c_export = st.columns([1.5, 1.5, 2])
        with c_del_batch:
            if not selected_rows.empty:
                if st.button(f"🗑️ 刪除勾選項 ({len(selected_rows)} 筆)", type="primary", key="btn_del_batch_fa"):
                    ids_to_del = selected_rows["id"].tolist()
                    safe_batch_delete(supabase, ids_to_del)
                    st.success(f"已刪除 {len(ids_to_del)} 筆固定資產！")
                    st.rerun()
        with c_clear_all:
            if st.button("💣 一鍵清空所有固定資產", key="btn_clear_fa"):
                supabase.table("assets").delete().eq("asset_type", "固定資產").execute()
                st.success("已清空固定資產！")
                st.rerun()
        with c_export:
            csv = display_df.drop(columns=["選取", "id"], errors="ignore").to_csv(index=False).encode('utf-8-sig')
            filename = generate_export_filename("固定資產清單", wh_filter, status_filter)
            st.download_button(f"📥 匯出清單 ({filename})", csv, filename, "text/csv")
    else:
        st.info("尚無符合條件的固定資產。")

    st.divider()
    c_add, c_del_quick = st.columns(2)

    with c_add.expander("➕ 快速新增固定資產", expanded=False):
        with st.form("add_fa_form"):
            col_fa_1, col_fa_2 = st.columns(2)
            fa_tag = col_fa_1.text_input("資產編號")
            fa_desc = col_fa_2.text_input("物料描述 (必填，如: MacBook Pro 14)")
            fa_wh = col_fa_1.selectbox("庫別", RAW_WAREHOUSE_OPTIONS, index=0)
            fa_cat = col_fa_2.text_input("分類", value="資訊設備")
            fa_holder = col_fa_1.text_input("使用人 / 保管部門")
            fa_uid = col_fa_2.text_input("使用人工號")
            fa_geo = col_fa_1.text_input("地理位置", value="台北辦公室")
            fa_loc = col_fa_2.text_input("詳細地點 (如: 7F 機房/桌號)")
            fa_status = col_fa_1.selectbox("狀態", RAW_STATUS_OPTIONS, index=2)
            fa_notes = st.text_area("備註說明")
            
            btn_add_fa = st.form_submit_button("確認新增固定資產")
            if btn_add_fa:
                if not fa_desc:
                    st.error("物料描述為必填項！")
                else:
                    try:
                        supabase.table("assets").insert({
                            "asset_tag": fa_tag.strip() if fa_tag else None,
                            "name": fa_desc.strip(),
                            "material_desc": fa_desc.strip(),
                            "asset_type": "固定資產",
                            "warehouse_type": fa_wh,
                            "category": fa_cat.strip() if fa_cat else "資訊設備",
                            "holder_name": fa_holder.strip() if fa_holder else None,
                            "user_id_code": fa_uid.strip() if fa_uid else None,
                            "geo_location": fa_geo.strip(),
                            "detailed_location": fa_loc.strip(),
                            "location": fa_geo.strip(),
                            "status": fa_status,
                            "notes": fa_notes.strip() if fa_notes else None
                        }).execute()
                        st.success("🎉 固定資產新增成功！")
                        st.rerun()
                    except Exception as e:
                        st.error(f"新增失敗：{str(e)}")

    with c_del_quick.expander("🗑️ 輸入資產編號直接刪除", expanded=False):
        with st.form("del_by_code_fa"):
            del_tag_input = st.text_input("請輸入欲刪除的「資產編號」")
            confirm_check = st.checkbox("⚠️ 我確定要刪除這筆資產")
            btn_del_code = st.form_submit_button("立即刪除")
            if btn_del_code:
                if not del_tag_input.strip():
                    st.warning("請先輸入資產編號！")
                elif not confirm_check:
                    st.warning("請先勾選確認框！")
                else:
                    res = supabase.table("assets").delete().eq("asset_tag", del_tag_input.strip()).execute()
                    if res.data:
                        st.success(f"🗑️️ 已成功刪除資產編號：{del_tag_input.strip()}")
                        st.rerun()
                    else:
                        st.error("查無此資產編號！")

# ========================================================
# 2. 低值品
# ========================================================
elif menu == "📦 低值品":
    st.header("📦 低值品管理")
    
    raw_df = supabase.table("assets").select("*").eq("asset_type", "低值品").execute().data
    if raw_df:
        render_metric_header(pd.DataFrame(raw_df))
        
    lv_cats = get_category_counts(["低值品"])
    status_filter, wh_filter, cat_filter, keyword = render_filter_and_search("低值品", lv_cats, "資產編號 / 資物料描述 / 使用人 / 工號")
    df = fetch_and_filter_data(["低值品"], status_filter, wh_filter, cat_filter, keyword)
    
    if not df.empty:
        col_map = {
            "asset_tag": "資產編號",
            "material_desc": "資物料描述",
            "warehouse_type": "庫別",
            "category": "分類",
            "holder_name": "使用人",
            "user_id_code": "使用人工號",
            "status": "狀態",
            "location": "位置",
            "notes": "備註"
        }
        df["material_desc"] = df["material_desc"].fillna(df.get("name", ""))
        df["location"] = df["location"].fillna(df.get("geo_location", ""))
        df["warehouse_type"] = df["warehouse_type"].fillna("個人倉")
        df["status"] = df["status"].apply(format_status_badge)
        display_df = clean_display_df(df, col_map)
        
        c_sel_all, c_info = st.columns([1.2, 3.8])
        select_all_lv = c_sel_all.checkbox("🔘 全選此畫面資料", key="select_all_lv")
        c_info.caption(f"顯示共 {len(display_df)} 筆低值品")
        
        display_df.insert(0, "選取", select_all_lv)
        
        # 黃金比例排版
        edited_df = st.data_editor(
            display_df,
            hide_index=True,
            use_container_width=True,
            height=600,
            key="editor_lv",
            column_config={
                "id": None,
                "選取": st.column_config.CheckboxColumn("選取", width="small", default=select_all_lv),
                "資產編號": st.column_config.TextColumn("資產編號", width="medium"),
                "資物料描述": st.column_config.TextColumn("資物料描述", width="large"),
                "庫別": st.column_config.TextColumn("庫別", width="small"),
                "分類": st.column_config.TextColumn("分類", width="small"),
                "使用人": st.column_config.TextColumn("使用人", width="small"),
                "使用人工號": st.column_config.TextColumn("使用人工號", width="small"),
                "狀態": st.column_config.TextColumn("狀態", width="small"),
                "位置": st.column_config.TextColumn("位置", width="small"),
                "備註": st.column_config.TextColumn("備註", width="medium")
            },
            disabled=[c for c in display_df.columns if c != "選取"]
        )
        
        selected_rows = edited_df[edited_df["選取"] == True]
        c_del_batch, c_clear_all, c_export = st.columns([1.5, 1.5, 2])
        with c_del_batch:
            if not selected_rows.empty:
                if st.button(f"🗑️ 刪除勾選項 ({len(selected_rows)} 筆)", type="primary", key="btn_del_batch_lv"):
                    ids_to_del = selected_rows["id"].tolist()
                    safe_batch_delete(supabase, ids_to_del)
                    st.success(f"已刪除 {len(ids_to_del)} 筆低值品！")
                    st.rerun()
        with c_clear_all:
            if st.button("💣 一鍵清空所有低值品", key="btn_clear_lv"):
                supabase.table("assets").delete().eq("asset_type", "低值品").execute()
                st.success("已清空低值品！")
                st.rerun()
        with c_export:
            csv = display_df.drop(columns=["選取", "id"], errors="ignore").to_csv(index=False).encode('utf-8-sig')
            filename = generate_export_filename("低值品清單", wh_filter, status_filter)
            st.download_button(f"📥 匯出清單 ({filename})", csv, filename, "text/csv")
    else:
        st.info("尚無符合條件的低值品資料。")

    st.divider()
    c_add, c_del_quick = st.columns(2)

    with c_add.expander("➕ 快速新增低值品", expanded=False):
        with st.form("add_low_val_form"):
            col_lv_1, col_lv_2 = st.columns(2)
            lv_tag = col_lv_1.text_input("資產編號 (無可留空)")
            lv_desc = col_lv_2.text_input("資物料描述 (必填，如: 羅技無線滑鼠)")
            lv_wh = col_lv_1.selectbox("庫別", RAW_WAREHOUSE_OPTIONS, index=0)
            lv_cat = col_lv_2.text_input("分類", value="硬碟/記憶體/周邊")
            lv_holder = col_lv_1.text_input("使用人 / 保管單位")
            lv_uid = col_lv_2.text_input("使用人工號")
            lv_loc = col_lv_1.text_input("位置", value="台北辦公室")
            lv_status = col_lv_2.selectbox("狀態", RAW_STATUS_OPTIONS, index=2)
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
                            "warehouse_type": lv_wh,
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

    with c_del_quick.expander("🗑️ 輸入編號/描述直接刪除", expanded=False):
        with st.form("del_by_code_lv"):
            del_input = st.text_input("輸入欲刪除的「資產編號」或「物料描述」")
            confirm_check = st.checkbox("⚠️ 我確定要刪除")
            btn_del_lv = st.form_submit_button("立即刪除")
            if btn_del_lv:
                if not del_input.strip():
                    st.warning("請輸入內容！")
                elif not confirm_check:
                    st.warning("請先勾選確認框！")
                else:
                    target = del_input.strip()
                    res = supabase.table("assets").delete().or_(f"asset_tag.eq.{target},material_desc.eq.{target}").execute()
                    if res.data:
                        st.success(f"🗑️ 已成功刪除 {len(res.data)} 筆符合資料！")
                        st.rerun()
                    else:
                        st.error("查無符合資料！")

# ========================================================
# 3. 手機 (樣機/外購機)
# ========================================================
elif menu == "📱 手機 (樣機/外購機)":
    st.header("📱 手機 (樣機 / 外購機 / 測試機) 管理")
    
    phone_types = ["手機 (樣機/外購機)", "樣機", "外購機", "手機"]
    raw_df = supabase.table("assets").select("*").in_("asset_type", phone_types).execute().data
    if raw_df:
        render_metric_header(pd.DataFrame(raw_df))
        
    ph_cats = get_category_counts(phone_types)
    status_filter, wh_filter, cat_filter, keyword = render_filter_and_search("手機", ph_cats, "PCB / IMEI / 物料描述 / 使用人")
    df = fetch_and_filter_data(phone_types, status_filter, wh_filter, cat_filter, keyword)
    
    if not df.empty:
        col_map = {
            "pcb_no": "PCB",
            "material_desc": "物料描述",
            "warehouse_type": "庫別",
            "imei_no": "IMEI",
            "material_code": "物料代碼",
            "holder_name": "使用人",
            "user_id_code": "使用人工號",
            "status": "狀態",
            "notes": "備註"
        }
        df["material_desc"] = df["material_desc"].fillna(df.get("name", ""))
        df["warehouse_type"] = df["warehouse_type"].fillna("個人倉")
        df["status"] = df["status"].apply(format_status_badge)
        display_df = clean_display_df(df, col_map)
        
        c_sel_all, c_info = st.columns([1.2, 3.8])
        select_all_ph = c_sel_all.checkbox("🔘 全選此畫面資料", key="select_all_ph")
        c_info.caption(f"顯示共 {len(display_df)} 筆手機設備")
        
        display_df.insert(0, "選取", select_all_ph)
        
        # 黃金比例排版
        edited_df = st.data_editor(
            display_df,
            hide_index=True,
            use_container_width=True,
            height=600,
            key="editor_ph",
            column_config={
                "id": None,
                "選取": st.column_config.CheckboxColumn("選取", width="small", default=select_all_ph),
                "PCB": st.column_config.TextColumn("PCB", width="medium"),
                "物料描述": st.column_config.TextColumn("物料描述", width="large"),
                "庫別": st.column_config.TextColumn("庫別", width="small"),
                "IMEI": st.column_config.TextColumn("IMEI", width="medium"),
                "物料代碼": st.column_config.TextColumn("物料代碼", width="small"),
                "使用人": st.column_config.TextColumn("使用人", width="small"),
                "使用人工號": st.column_config.TextColumn("使用人工號", width="small"),
                "狀態": st.column_config.TextColumn("狀態", width="small"),
                "備註": st.column_config.TextColumn("備註", width="medium")
            },
            disabled=[c for c in display_df.columns if c != "選取"]
        )
        
        selected_rows = edited_df[edited_df["選取"] == True]
        c_del_batch, c_clear_all, c_export = st.columns([1.5, 1.5, 2])
        with c_del_batch:
            if not selected_rows.empty:
                if st.button(f"🗑️ 刪除勾選項 ({len(selected_rows)} 筆)", type="primary", key="btn_del_batch_ph"):
                    ids_to_del = selected_rows["id"].tolist()
                    safe_batch_delete(supabase, ids_to_del)
                    st.success(f"已刪除 {len(ids_to_del)} 筆手機資料！")
                    st.rerun()
        with c_clear_all:
            if st.button("💣 一鍵清空所有手機設備", key="btn_clear_ph"):
                supabase.table("assets").delete().in_("asset_type", phone_types).execute()
                st.success("已清空手機資料！")
                st.rerun()
        with c_export:
            csv = display_df.drop(columns=["選取", "id"], errors="ignore").to_csv(index=False).encode('utf-8-sig')
            filename = generate_export_filename("手機樣機清單", wh_filter, status_filter)
            st.download_button(f"📥 匯出清單 ({filename})", csv, filename, "text/csv")
    else:
        st.info("尚無符合條件的手機資料。")

    st.divider()
    c_add, c_del_quick = st.columns(2)

    with c_add.expander("➕ 快速新增手機設備 (樣機/外購機)", expanded=False):
        with st.form("add_phone_form"):
            ph_desc = st.text_input("物料描述 (必填，如: Pixel 8 測試機 / iPhone 15)")
            col_p1, col_p2 = st.columns(2)
            ph_wh = col_p1.selectbox("庫別", RAW_WAREHOUSE_OPTIONS, index=0)
            ph_pcb = col_p2.text_input("PCB 號碼")
            ph_imei = col_p1.text_input("IMEI 號碼")
            ph_code = col_p2.text_input("物料代碼")
            ph_holder = col_p1.text_input("使用人 / 借測單位")
            ph_uid = col_p2.text_input("使用人工號")
            ph_status = col_p1.selectbox("狀態", RAW_STATUS_OPTIONS, index=2)
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
                            "warehouse_type": ph_wh,
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

    with c_del_quick.expander("🗑️ 輸入 IMEI / PCB / 代碼直接刪除", expanded=False):
        with st.form("del_by_code_phone"):
            del_p_input = st.text_input("輸入欲刪除的「IMEI」或「PCB 號碼」或「物料代碼」")
            confirm_check = st.checkbox("⚠️ 我確定要刪除")
            btn_del_phone = st.form_submit_button("立即刪除")
            if btn_del_phone:
                if not del_p_input.strip():
                    st.warning("請先輸入識別碼！")
                elif not confirm_check:
                    st.warning("請先勾選確認框！")
                else:
                    target = del_p_input.strip()
                    res = supabase.table("assets").delete().or_(f"imei_no.eq.{target},pcb_no.eq.{target},material_code.eq.{target}").execute()
                    if res.data:
                        st.success(f"🗑️ 已成功刪除 {len(res.data)} 筆手機資料！")
                        st.rerun()
                    else:
                        st.error("查無符合資料！")

# ========================================================
# 4. 物料管理
# ========================================================
elif menu == "🔩 物料管理":
    st.header("🔩 物料管理")
    
    raw_df = supabase.table("assets").select("*").in_("asset_type", ["物料", "耗材與物料"]).execute().data
    if raw_df:
        render_metric_header(pd.DataFrame(raw_df))
        
    mat_cats = get_category_counts(["物料", "耗材與物料"])
    status_filter, wh_filter, cat_filter, keyword = render_filter_and_search("物料", mat_cats, "物料代碼 / PCB / 物料描述 / 使用人")
    df = fetch_and_filter_data(["物料", "耗材與物料"], status_filter, wh_filter, cat_filter, keyword)
    
    if not df.empty:
        col_map = {
            "material_code": "物料代碼",
            "pcb_no": "IMEI／PCB",
            "material_desc": "物料描述",
            "warehouse_type": "庫別",
            "holder_name": "使用人",
            "user_id_code": "使用人工號",
            "quantity": "數量",
            "status": "狀態",
            "notes": "備註"
        }
        df["material_desc"] = df["material_desc"].fillna(df.get("name", ""))
        df["pcb_no"] = df["pcb_no"].fillna(df.get("imei_no", ""))
        df["warehouse_type"] = df["warehouse_type"].fillna("部門倉")
        df["status"] = df["status"].apply(format_status_badge)
        display_df = clean_display_df(df, col_map)
        
        c_sel_all, c_info = st.columns([1.2, 3.8])
        select_all_mat = c_sel_all.checkbox("🔘 全選此畫面資料", key="select_all_mat")
        c_info.caption(f"顯示共 {len(display_df)} 筆物料項目")
        
        display_df.insert(0, "選取", select_all_mat)
        
        # 黃金比例排版
        edited_df = st.data_editor(
            display_df,
            hide_index=True,
            use_container_width=True,
            height=600,
            key="editor_mat",
            column_config={
                "id": None,
                "選取": st.column_config.CheckboxColumn("選取", width="small", default=select_all_mat),
                "物料代碼": st.column_config.TextColumn("物料代碼", width="medium"),
                "IMEI／PCB": st.column_config.TextColumn("IMEI／PCB", width="medium"),
                "物料描述": st.column_config.TextColumn("物料描述", width="large"),
                "庫別": st.column_config.TextColumn("庫別", width="small"),
                "使用人": st.column_config.TextColumn("使用人", width="small"),
                "使用人工號": st.column_config.TextColumn("使用人工號", width="small"),
                "數量": st.column_config.NumberColumn("數量", width="small"),
                "狀態": st.column_config.TextColumn("狀態", width="small"),
                "備註": st.column_config.TextColumn("備註", width="medium")
            },
            disabled=[c for c in display_df.columns if c != "選取"]
        )
        
        selected_rows = edited_df[edited_df["選取"] == True]
        c_del_batch, c_clear_all, c_export = st.columns([1.5, 1.5, 2])
        with c_del_batch:
            if not selected_rows.empty:
                if st.button(f"🗑️ 刪除勾選項 ({len(selected_rows)} 筆)", type="primary", key="btn_del_batch_mat"):
                    ids_to_del = selected_rows["id"].tolist()
                    safe_batch_delete(supabase, ids_to_del)
                    st.success(f"已刪除 {len(ids_to_del)} 筆物料！")
                    st.rerun()
        with c_clear_all:
            if st.button("💣 一鍵清空所有物料", key="btn_clear_mat"):
                supabase.table("assets").delete().in_("asset_type", ["物料", "耗材與物料"]).execute()
                st.success("已清空物料！")
                st.rerun()
        with c_export:
            csv = display_df.drop(columns=["選取", "id"], errors="ignore").to_csv(index=False).encode('utf-8-sig')
            filename = generate_export_filename("物料清單", wh_filter, status_filter)
            st.download_button(f"📥 匯出清單 ({filename})", csv, filename, "text/csv")
    else:
        st.info("尚無符合條件的物料資料。")

# ========================================================
# 5. 狀態異動與轉移
# ========================================================
elif menu == "🔄 狀態異動與轉移":
    st.header("🔄 資產狀態轉移與使用人/庫別變更")
    
    asset_query_input = st.text_input("輸入欲異動之「資產編號」或「IMEI」或「PCB」或「物料代碼」")
    
    if asset_query_input:
        kw = asset_query_input.strip()
        res = supabase.table("assets").select("*").or_(
            f"asset_tag.eq.{kw},imei_no.eq.{kw},pcb_no.eq.{kw},material_code.eq.{kw}"
        ).execute()
        
        if res.data:
            item = res.data[0]
            curr_wh = item.get("warehouse_type") or "個人倉"
            curr_holder = item.get('holder_name') or '無'
            curr_code = f" ({item.get('user_id_code')})" if item.get('user_id_code') else ""
            st.success(f"找到設備：[{item.get('asset_type')}] {item.get('material_desc') or item.get('name')} | 現屬【{curr_wh}】 | 狀態：【{item['status']}】 | 目前保管人：{curr_holder}{curr_code}")
            
            with st.form("transfer_form"):
                col_t1, col_t2 = st.columns(2)
                new_status = col_t1.selectbox("變更後狀態", RAW_STATUS_OPTIONS, index=RAW_STATUS_OPTIONS.index(item['status']) if item['status'] in RAW_STATUS_OPTIONS else 0)
                new_wh = col_t2.selectbox("變更後庫別", RAW_WAREHOUSE_OPTIONS, index=RAW_WAREHOUSE_OPTIONS.index(curr_wh) if curr_wh in RAW_WAREHOUSE_OPTIONS else 0)
                
                col_u1, col_u2 = st.columns(2)
                new_holder = col_u1.text_input("新使用人 / 保管單位姓名", value=item.get("holder_name") or "")
                new_user_id = col_u2.text_input("新使用人工號", value=item.get("user_id_code") or "")
                
                col_l1, col_l2 = st.columns(2)
                new_geo = col_l1.text_input("地理位置", value=item.get("geo_location") or item.get("location") or "台北辦公室")
                new_detail_loc = col_l2.text_input("詳細地點", value=item.get("detailed_location") or "")
                
                transfer_remark = st.text_area("本次異動備註 (如: 撥轉至部門公共機房、個人歸還入庫)")
                operator = st.text_input("經辦人姓名", value="Admin")
                
                btn_transfer = st.form_submit_button("確認提交更新")
                if btn_transfer:
                    supabase.table("assets").update({
                        "status": new_status,
                        "warehouse_type": new_wh,
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
                        "action_type": f"變更狀態為-{new_status}({new_wh})",
                        "previous_holder": item.get("holder_name"),
                        "new_holder": new_holder,
                        "operator": operator,
                        "remark": f"[庫別: {new_wh} | 工號: {new_user_id}] {transfer_remark}"
                    }).execute()
                    
                    st.success("✅ 狀態與庫別已同步更新至 Supabase！")
        else:
            st.error("查無此編號/IMEI/PCB/物料代碼，請重新確認。")

# ========================================================
# 6. 批次匯入
# ========================================================
elif menu == "📥 批次匯入 (Excel/CSV)":
    st.header("📥 資產資料批次匯入")
    st.write("直接上傳公司現有的 Excel (`.xlsx`) 或 CSV 檔案，支援「個人倉」與「部門倉」自動辨識。")
    
    with st.expander("📄 點此下載標準匯入範本 (CSV) 與查看支援欄位說明", expanded=True):
        sample_df = pd.DataFrame([
            {
                "資產主類型": "固定資產",
                "庫別": "個人倉",
                "資產編號": "FA-2026-001",
                "物料描述": "Dell 27吋 4K 螢幕",
                "分類": "螢幕設備",
                "物料代碼": "",
                "PCB": "",
                "IMEI": "",
                "使用人": "王小明",
                "使用人工號": "EMP0123",
                "狀態": "使用中",
                "地理位置": "台北辦公室",
                "詳細地點": "7F 開放辦公區-桌號12",
                "數量": 1,
                "備註": "雙螢幕配置之一"
            },
            {
                "資產主類型": "低值品",
                "庫別": "部門倉",
                "資產編號": "888220-1",
                "物料描述": "SAMSUNG 970 EVO Plus 1TB SSD",
                "分類": "硬碟",
                "物料代碼": "",
                "PCB": "",
                "IMEI": "",
                "使用人": "IT部門公用",
                "使用人工號": "",
                "狀態": "閒置",
                "地理位置": "台北辦公室",
                "詳細地點": "IT測試機房備料架",
                "數量": 1,
                "備註": "桌機升級用備料"
            }
        ])
        
        sample_csv = sample_df.to_csv(index=False).encode('utf-8-sig')
        st.download_button(
            label="📥 點擊下載標準匯入範本 (CSV 格式)",
            data=sample_csv,
            file_name="企業資產統一標準匯入範本.csv",
            mime="text/csv"
        )
        st.dataframe(sample_df, use_container_width=True, hide_index=True)
    
    st.divider()
    uploaded_file = st.file_uploader("請選擇要匯入的 Excel 或 CSV 檔案", type=["csv", "xlsx"])
    
    if uploaded_file is not None:
        try:
            if uploaded_file.name.endswith(".csv"):
                df_up = pd.read_csv(uploaded_file)
            else:
                df_up = pd.read_excel(uploaded_file)
                
            df_up.columns = [str(c).strip() for c in df_up.columns]
            
            st.subheader("預覽即將匯入的資料（前 5 筆）：")
            st.dataframe(df_up.head(), use_container_width=True)
            
            col_map = {
                "資產主類型": "asset_type", "資產類型": "asset_type", "類型": "asset_type",
                "庫別": "warehouse_type", "倉庫": "warehouse_type", "倉別": "warehouse_type",
                "資產編號": "asset_tag", "設備編號": "asset_tag", "編號": "asset_tag", "asset_tag": "asset_tag",
                "物料描述": "material_desc", "資物料描述": "material_desc", "設備名稱": "material_desc", "品名": "material_desc", "規格": "material_desc", "名稱": "material_desc",
                "物料代碼": "material_code", "料號": "material_code",
                "分類": "category", "類別": "category", "設備分類": "category",
                "PCB": "pcb_no", "PCB號碼": "pcb_no", "PCB NO": "pcb_no",
                "IMEI": "imei_no", "IMEI號碼": "imei_no", "IMEI／PCB": "pcb_no", "IMEI/PCB": "pcb_no",
                "使用人": "holder_name", "保管人": "holder_name", "借用人": "holder_name", "姓名": "holder_name",
                "使用人工號": "user_id_code", "工號": "user_id_code", "員工編號": "user_id_code", "員編": "user_id_code",
                "狀態": "status",
                "地理位置": "geo_location", "位置": "location", "存放地點": "geo_location",
                "詳細地點": "detailed_location", "詳細位置": "detailed_location",
                "數量": "quantity",
                "備註": "notes", "備註說明": "notes"
            }
            
            c_in_type, c_in_wh = st.columns(2)
            target_asset_type = c_in_type.selectbox(
                "若上傳檔案內無「資產主類型」欄位，預設歸類為：",
                ["低值品", "固定資產", "手機 (樣機/外購機)", "物料"]
            )
            target_wh_type = c_in_wh.selectbox(
                "若上傳檔案內無「庫別」欄位，預設歸類為：",
                ["個人倉", "部門倉"]
            )
            
            if st.button("🚀 確認將資料整批匯入 Supabase", type="primary"):
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
                        if atype_str in ["樣機", "外購機", "手機"]:
                            rec["asset_type"] = "手機 (樣機/外購機)"
                        else:
                            rec["asset_type"] = atype_str
                    else:
                        rec["asset_type"] = target_asset_type
                        
                    wh_val = row.get("warehouse_type")
                    if pd.notna(wh_val) and str(wh_val).strip() and str(wh_val).strip().lower() != "nan":
                        rec["warehouse_type"] = str(wh_val).strip()
                    else:
                        rec["warehouse_type"] = target_wh_type
                        
                    rec["quantity"] = int(row.get("quantity")) if pd.notna(row.get("quantity")) and str(row.get("quantity")).isdigit() else 1
                    
                    tag_v = row.get("asset_tag")
                    rec["asset_tag"] = str(tag_v).strip() if pd.notna(tag_v) and str(tag_v).strip().lower() != "nan" else None
                    
                    for k in ["material_code", "category", "pcb_no", "imei_no", "holder_name", "user_id_code", "geo_location", "detailed_location", "location", "notes"]:
                        val = row.get(k)
                        rec[k] = str(val).strip() if pd.notna(val) and str(val).strip().lower() != "nan" else None
                    
                    if not rec.get("location"):
                        rec["location"] = rec.get("geo_location") or "台北辦公室"
                    records.append(rec)
                
                batch_size = 50
                progress_bar = st.progress(0)
                for i in range(0, len(records), batch_size):
                    chunk = records[i:i + batch_size]
                    supabase.table("assets").insert(chunk).execute()
                    progress_bar.progress(min((i + batch_size) / len(records), 1.0))
                
                st.success(f"🎉 成功匯入 {len(records)} 筆資料至資料庫！")
                
        except Exception as e:
            st.error(f"匯入錯誤：{str(e)}")

# ========================================================
# 7. 統計看板
# ========================================================
elif menu == "📊 統計看板":
    st.header("📊 全公司資產分佈概況")
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
        g1, g2, g3 = st.columns(3)
        with g1:
            st.subheader("各大業務分類數量")
            st.bar_chart(df["asset_type"].fillna("未分類").value_counts())
        with g2:
            st.subheader("個人倉 vs 部門倉")
            if "warehouse_type" in df.columns:
                st.bar_chart(df["warehouse_type"].fillna("個人倉").value_counts())
        with g3:
            st.subheader("整體狀態分佈")
            st.bar_chart(df["status"].value_counts())
    else:
        st.info("尚無統計數據。")
