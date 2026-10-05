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
        "➕ 單筆建檔",
        "📥 批次匯入 (Excel/CSV)",
        "📊 統計看板"
    ]
)

# 通用過濾與搜尋小工具函式
def render_filter_and_search(placeholder_text="搜尋..."):
    c1, c2 = st.columns([1, 2])
    status_filter = c1.selectbox("狀態篩選", STATUS_OPTIONS, key=f"status_{menu}")
    keyword = c2.text_input(f"🔍 搜尋 ({placeholder_text})", key=f"kw_{menu}")
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
    # 將 None, nan 轉成乾淨的空字串
    return sub_df.fillna("").astype(str).replace({"None": "", "nan": ""})

# ========================================================
# 1. 固定資產
# ========================================================
if menu == "💼 固定資產":
    st.header("💼 固定資產清單")
    status_filter, keyword = render_filter_and_search("資產編號 / 物料描述 / 使用人 / 工號")
    
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
        # height=800 大幅拉長表格顯示高度
        st.dataframe(display_df, use_container_width=True, hide_index=True, height=800)
        
        csv = display_df.to_csv(index=False).encode('utf-8-sig')
        st.download_button("📥 匯出固定資產清單 (CSV)", csv, "固定資產清單.csv", "text/csv")
    else:
        st.info("目前尚無固定資產資料。")

# ========================================================
# 2. 低值品
# ========================================================
elif menu == "📦 低值品":
    st.header("📦 低值品清單")
    status_filter, keyword = render_filter_and_search("資產編號 / 物料描述 / 使用人 / 工號")
    
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
        st.dataframe(display_df, use_container_width=True, hide_index=True, height=800)
        
        csv = display_df.to_csv(index=False).encode('utf-8-sig')
        st.download_button("📥 匯出低值品清單 (CSV)", csv, "低值品清單.csv", "text/csv")
    else:
        st.info("目前尚無低值品資料。")

# ========================================================
# 3. 手機 (樣機/外購機)
# ========================================================
elif menu == "📱 手機 (樣機/外購機)":
    st.header("📱 手機 (樣機 / 外購機 / 測試機) 清單")
    status_filter, keyword = render_filter_and_search("PCB / IMEI / 物料描述 / 使用人")
    
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
        st.dataframe(display_df, use_container_width=True, hide_index=True, height=800)
        
        csv = display_df.to_csv(index=False).encode('utf-8-sig')
        st.download_button("📥 匯出手機清單 (CSV)", csv, "手機樣機清單.csv", "text/csv")
    else:
        st.info("目前尚無手機樣機/外購機資料。")

# ========================================================
# 4. 物料管理
# ========================================================
elif menu == "🔩 物料管理":
    st.header("🔩 物料清單")
    status_filter, keyword = render_filter_and_search("物料代碼 / PCB / 物料描述 / 使用人")
    
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
        st.dataframe(display_df, use_container_width=True, hide_index=True, height=800)
        
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
                        "asset_tag": item.get("asset_tag") or item.get("material_code") or "N/A",
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
# 6. 單筆建檔
# ========================================================
elif menu == "➕ 單筆建檔":
    st.header("建立新資產資料")
    asset_type = st.selectbox("欲新增的資產類型", ["固定資產", "低值品", "手機 (樣機/外購機)", "物料"])
    
    with st.form("new_single_asset"):
        col1, col2 = st.columns(2)
        
        if asset_type == "固定資產":
            tag = col1.text_input("資產編號")
            material_desc = col2.text_input("物料描述 (必填，如: MacBook Pro 14)")
            category = col1.text_input("分類", value="資訊設備")
            geo_loc = col2.text_input("地理位置", value="台北辦公室")
            detail_loc = col1.text_input("詳細地點 (如: 7F 機房 A 架)")
            holder = col2.text_input("使用人")
            user_id = col1.text_input("使用人工號")
            status = col2.selectbox("狀態", RAW_STATUS_OPTIONS, index=2)
            pcb_no, imei_no, mat_code, location, qty = None, None, None, geo_loc, 1

        elif asset_type == "低值品":
            tag = col1.text_input("資產編號")
            material_desc = col2.text_input("資物料描述 (必填，如: 羅技無線滑鼠)")
            category = col1.text_input("分類", value="周邊耗材")
            location = col2.text_input("位置", value="台北辦公室")
            holder = col1.text_input("使用人")
            user_id = col2.text_input("使用人工號")
            status = col1.selectbox("狀態", RAW_STATUS_OPTIONS, index=2)
            pcb_no, imei_no, mat_code, geo_loc, detail_loc, qty = None, None, None, location, "", 1

        elif asset_type == "手機 (樣機/外購機)":
            mat_code = col1.text_input("物料代碼")
            material_desc = col2.text_input("物料描述 (必填，如: Pixel 8 測試機)")
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
                    supabase.table("assets").insert(payload).execute()
                    st.success(f"🎉 [{asset_type}] 資料建立成功！")
                except Exception as e:
                    st.error(f"新增失敗：{str(e)}")

# ========================================================
# 7. 批次匯入 (擴大表頭容錯，支援各類工號、資產編號別名)
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
                
            # 去除表頭所有前後空格
            df_up.columns = [str(c).strip() for c in df_up.columns]
            
            st.write("預覽匯入資料（前 5 筆）：")
            st.dataframe(df_up.head(), use_container_width=True)
            
            # 超級表頭別名映射表
            col_map = {
                # 資產主類型
                "資產主類型": "asset_type", "資產類型": "asset_type", "類型": "asset_type",
                # 資產編號
                "資產編號": "asset_tag", "設備編號": "asset_tag", "編號": "asset_tag", "asset_tag": "asset_tag", "Asset Tag": "asset_tag", "標籤編號": "asset_tag",
                # 物料描述 / 規格名稱
                "物料描述": "material_desc", "資物料描述": "material_desc", "設備名稱": "material_desc", "品名": "material_desc", "規格": "material_desc", "名稱": "material_desc",
                # 物料代碼
                "物料代碼": "material_code", "料號": "material_code",
                # 分類
                "分類": "category", "類別": "category", "設備分類": "category",
                # PCB / IMEI
                "PCB": "pcb_no", "PCB號碼": "pcb_no", "PCB NO": "pcb_no",
                "IMEI": "imei_no", "IMEI號碼": "imei_no", "IMEI／PCB": "pcb_no", "IMEI/PCB": "pcb_no",
                # 人員與工號 (關鍵擴充)
                "使用人": "holder_name", "保管人": "holder_name", "借用人": "holder_name", "領用人": "holder_name", "姓名": "holder_name",
                "使用人工號": "user_id_code", "工號": "user_id_code", "員工編號": "user_id_code", "員編": "user_id_code", "使用者工號": "user_id_code", "員工代號": "user_id_code",
                # 狀態
                "狀態": "status", "設備狀態": "status",
                # 地點
                "地理位置": "geo_location", "位置": "location", "存放地點": "geo_location",
                "詳細地點": "detailed_location", "詳細位置": "detailed_location",
                # 數量與備註
                "數量": "quantity",
                "備註": "notes", "備註說明": "notes"
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
                    
                    # 狀態正規化
                    st_val = str(row.get("status") or "").strip()
                    if st_val in ["在用中", "使用中"]:
                        rec["status"] = "使用中"
                    elif st_val in ["轉移中", "備用", "待報廢"]:
                        rec["status"] = st_val
                    else:
                        rec["status"] = "閒置"
                        
                    # 類型正規化
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
                    
                    # 處理資產編號
                    tag_v = row.get("asset_tag")
                    rec["asset_tag"] = str(tag_v).strip() if pd.notna(tag_v) and str(tag_v).strip().lower() != "nan" else None
                    
                    for k in ["material_code", "category", "pcb_no", "imei_no", "holder_name", "user_id_code", "geo_location", "detailed_location", "location", "notes"]:
                        val = row.get(k)
                        rec[k] = str(val).strip() if pd.notna(val) and str(val).strip().lower() != "nan" else None
                    
                    if not rec.get("location"):
                        rec["location"] = rec.get("geo_location") or "台北辦公室"
                    records.append(rec)
                
                supabase.table("assets").insert(records).execute()
                st.success(f"🎉 成功匯入 {len(records)} 筆資料至【{target_asset_type}】！已解決工號與編號問題。")
                
        except Exception as e:
            st.error(f"匯入錯誤：{str(e)}")

# ========================================================
# 8. 統計看板
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
