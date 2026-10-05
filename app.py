import streamlit as st
import pandas as pd
from datetime import datetime
from supabase import create_client, Client

st.set_page_config(
    page_title="企業資產管理系統",
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

# 側邊欄導航
st.sidebar.title("🏢 資產管理資料庫")
menu = st.sidebar.radio(
    "功能模組",
    ["📊 統計總覽", "📋 資產清單與查詢", "🔄 設備借還/異動移交", "➕ 新增資產"]
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
            st.subheader("設備類別分佈")
            cat_counts = df["category"].value_counts()
            st.bar_chart(cat_counts)
        with c2:
            st.subheader("存放地點分佈")
            loc_counts = df["location"].value_counts()
            st.bar_chart(loc_counts)
    else:
        st.info("目前資料庫內尚無資產資料，請至「新增資產」建立第一筆設備。")

# ----------------- 模組 2: 資產清單與查詢 -----------------
elif menu == "📋 資產清單與查詢":
    st.header("資產檢索清單")
    
    c1, c2, c3 = st.columns([2, 1, 1])
    search_keyword = c1.text_input("🔍 搜尋 (資產編號 / S/N / 設備名稱 / 保管人)")
    status_filter = c2.selectbox("狀態篩選", ["全部", "在庫", "使用中", "借測中", "維修中", "報廢"])
    loc_filter = c3.text_input("地點過濾 (如: 台北辦公室)")

    query = supabase.table("assets").select("*")
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

        cols_to_show = [c for c in ["asset_tag", "name", "category", "status", "holder_name", "holder_department", "location", "serial_number"] if c in df.columns]
        st.dataframe(df[cols_to_show], use_container_width=True, hide_index=True)

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
            st.success(f"找到設備：{asset['name']} (目前狀態：{asset['status']}，目前保管人：{asset['holder_name'] or '無'})")
            
            with st.form("transfer_form"):
                action = st.selectbox("異動動作", ["領用配發", "設備借測", "歸還入庫", "送修", "報廢"])
                new_holder = st.text_input("新保管人姓名 (歸還/送修/報廢可留空)")
                new_dept = st.text_input("新保管人部門")
                operator = st.text_input("經辦人姓名", value="Admin")
                remark = st.text_area("備註事由 (如：短期借測、面板故障維修)")
                
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

# ----------------- 模組 4: 新增資產 -----------------
elif menu == "➕ 新增資產":
    st.header("建立新資產資料")
    
    with st.form("new_asset_form"):
        col1, col2 = st.columns(2)
        tag = col1.text_input("資產編號 (必填，如 NB-2026-001)")
        sn = col2.text_input("原廠序號 S/N")
        name = col1.text_input("設備型號名稱 (必填，如 MacBook Pro 14)")
        
        cat_data = supabase.table("asset_categories").select("name").execute().data
        cat_options = [c["name"] for c in cat_data] if cat_data else ["筆記型電腦", "公務手機/測試機", "螢幕"]
        category = col2.selectbox("設備分類", cat_options)
        
        location = col1.text_input("存放地點", value="台北辦公室")
        cost = col2.number_input("採購金額", min_value=0.0, step=100.0)
        notes = st.text_area("規格與備註")
        
        submit_btn = st.form_submit_button("新增至資料庫")
        if submit_btn:
            if not tag or not name:
                st.error("資產編號與設備型號為必填項！")
            else:
                try:
                    insert_res = supabase.table("assets").insert({
                        "asset_tag": tag.strip(),
                        "serial_number": sn.strip() if sn else None,
                        "name": name.strip(),
                        "category": category,
                        "status": "在庫",
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
                            "remark": "初次建立入庫"
                        }).execute()
                    st.success(f"🎉 資產 {tag} 建立成功！")
                except Exception as e:
                    st.error(f"建立失敗：{str(e)}")
