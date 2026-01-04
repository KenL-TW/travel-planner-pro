import json
import pandas as pd
import streamlit as st

from db import init_db
from modals import CATEGORIES, TASK_STATUS
import services as svc


# -----------------------
# Streamlit Config
# -----------------------
st.set_page_config(page_title="Travel Planner Pro", page_icon="✈️", layout="wide")
init_db()

st.markdown("## ✈️ Travel Planner Pro（Streamlit）")
st.caption("旅行規劃 × 團隊任務指派 × 篩選看板 × SQLite 落地（可部署、可備份、可匯出）")
st.divider()


# -----------------------
# Sidebar: Trip Selection / Create / Import
# -----------------------
with st.sidebar:
    st.markdown("### 旅程管理")
    trips = svc.list_trips()
    if not trips:
        tid = svc.create_trip()
        trips = svc.list_trips()
        st.success("已自動建立第一個旅程。")

    trip_options = {f"{t['trip_title']}  ({t['destination']})": t["trip_id"] for t in trips}
    selected_label = st.selectbox("選擇旅程", options=list(trip_options.keys()))
    trip_id = trip_options[selected_label]

    st.write("")

    with st.expander("➕ 建立新旅程", expanded=False):
        st.caption("💡 快速開始：只需填寫目的地，其他可稍後編輯")
        
        # 快速模板選擇
        quick_template = st.selectbox(
            "🎯 快速模板（可選）",
            options=["自訂", "日本旅遊", "歐洲旅遊", "東南亞", "國內旅遊"],
            index=0
        )
        
        # 根據模板設定預設值
        template_defaults = {
            "日本旅遊": {"title": "日本之旅", "dest": "東京", "currency": "JPY"},
            "歐洲旅遊": {"title": "歐洲之旅", "dest": "巴黎", "currency": "EUR"},
            "東南亞": {"title": "東南亞之旅", "dest": "曼谷", "currency": "THB"},
            "國內旅遊": {"title": "台灣旅遊", "dest": "台北", "currency": "TWD"},
            "自訂": {"title": "新旅程", "dest": "", "currency": "TWD"}
        }
        
        defaults = template_defaults.get(quick_template, template_defaults["自訂"])
        
        # 簡化輸入欄位
        col1, col2 = st.columns(2)
        with col1:
            nt_title = st.text_input("旅程名稱 *", value=defaults["title"], placeholder="例：2026 春季日本行")
            nt_currency = st.selectbox("幣別 *", options=["TWD", "JPY", "USD", "EUR", "KRW", "CNY", "THB", "SGD"], 
                                      index=["TWD", "JPY", "USD", "EUR", "KRW", "CNY", "THB", "SGD"].index(defaults["currency"]))
        with col2:
            nt_dest = st.text_input("目的地 *", value=defaults["dest"], placeholder="例：東京、大阪")
        
        # 使用日期選擇器
        with st.expander("📅 設定日期（可選，稍後可編輯）"):
            from datetime import date, timedelta
            date_col1, date_col2 = st.columns(2)
            with date_col1:
                nt_start_date = st.date_input("開始日", value=None, format="YYYY-MM-DD")
            with date_col2:
                nt_end_date = st.date_input("結束日", value=None, format="YYYY-MM-DD")
        
        st.write("")
        if st.button("✨ 立即建立", use_container_width=True, type="primary"):
            if not nt_dest.strip():
                st.error("請至少填寫目的地！")
            else:
                new_id = svc.create_trip({
                    "tripTitle": nt_title,
                    "destination": nt_dest,
                    "startDate": str(nt_start_date) if nt_start_date else "",
                    "endDate": str(nt_end_date) if nt_end_date else "",
                    "currency": nt_currency,
                })
                st.success("✅ 建立完成！")
                st.rerun()

    st.write("")
    st.markdown("---")
    st.markdown("### 🔍 智慧篩選")
    st.caption("快速找到特定事件或任務")

    # Filters - will be applied in Task Board and Events list
    f_keyword = st.text_input("🔎 關鍵字搜尋", value="", placeholder="搜尋標題、地點或任務內容")
    f_category = st.multiselect("🏷️ 事件分類", options=CATEGORIES, default=[])
    f_status = st.multiselect("📊 任務狀態", options=TASK_STATUS, default=[])

    st.write("")
    if any([f_keyword, f_category, f_status]):
        st.info("🎯 已套用篩選條件")
    else:
        st.caption("💡 提示：篩選器會同時影響『行程規劃』和『任務看板』頁籤")


# -----------------------
# Load bundle
# -----------------------
bundle = svc.get_trip(trip_id)
trip = bundle["trip"]
days = bundle["days"]
members = bundle["members"]
checklists = bundle["checklists"]

member_map = {m["member_id"]: m["name"] for m in members}
member_choices = ["（未指派）"] + [f"{m['name']} ({m.get('role','')})".strip() for m in members]
member_choice_to_id = {"（未指派）": None}
for m in members:
    member_choice_to_id[f"{m['name']} ({m.get('role','')})".strip()] = m["member_id"]


# -----------------------
# Top Summary
# -----------------------
def compute_trip_stats(days_):
    total_cost = 0.0
    total_tasks = 0
    done_tasks = 0
    cat_cost = {c: 0.0 for c in CATEGORIES}

    all_tasks = []
    all_events = []

    for d in days_:
        for e in d.get("events", []):
            all_events.append(e)
            total_cost += float(e.get("cost") or 0)
            cat = e.get("category") or "其他"
            if cat in cat_cost:
                cat_cost[cat] += float(e.get("cost") or 0)
            for t in e.get("tasks", []):
                all_tasks.append(t)
                total_tasks += 1
                if t.get("status") == "done":
                    done_tasks += 1
                # backward compat: if old boolean completed exists
                if t.get("completed") is True:
                    done_tasks += 1

    progress = round((done_tasks/total_tasks)*100) if total_tasks else 0
    return total_cost, total_tasks, done_tasks, progress, cat_cost, all_events, all_tasks


total_cost, total_tasks, done_tasks, progress, cat_cost, all_events, all_tasks = compute_trip_stats(days)

kpi1, kpi2, kpi3 = st.columns([1.1, 1.1, 1.8], gap="large")
with kpi1:
    st.metric("任務完成", f"{done_tasks}/{total_tasks}", f"{progress}%")
with kpi2:
    st.metric("預估支出", f"{trip['currency']} {total_cost:,.0f}")
with kpi3:
    df_cat = pd.DataFrame([{"分類": k, "成本": v} for k, v in cat_cost.items()]).sort_values("成本", ascending=False)
    st.caption("預算分佈（分類）")
    st.bar_chart(df_cat.set_index("分類"), height=120)

st.divider()


# -----------------------
# Tabs
# -----------------------
tab_plan, tab_tasks, tab_team, tab_check = st.tabs(["🗓️ 行程規劃", "📌 任務看板", "👥 旅遊團隊", "✅ 準備清單"])


# -----------------------
# Tab: 行程規劃
# -----------------------
with tab_plan:
    left, right = st.columns([2.2, 1.0], gap="large")

    with left:
        st.subheader("旅程資訊")
        c1, c2, c3, c4, c5 = st.columns([1.6, 1.4, 1.0, 1.0, 0.8], gap="small")
        with c1:
            new_title = st.text_input("旅程名稱", value=trip["trip_title"])
        with c2:
            new_dest = st.text_input("目的地", value=trip["destination"])
        with c3:
            new_start = st.text_input("開始日", value=trip.get("start_date") or "")
        with c4:
            new_end = st.text_input("結束日", value=trip.get("end_date") or "")
        with c5:
            new_curr = st.text_input("幣別", value=trip["currency"], max_chars=6)

        if st.button("保存旅程資訊", use_container_width=True):
            svc.update_trip(trip_id, {
                "trip_title": new_title,
                "destination": new_dest,
                "start_date": new_start,
                "end_date": new_end,
                "currency": new_curr
            })
            st.success("已保存。")
            st.rerun()

        st.write("")
        st.subheader("行程時間線")

        if st.button("➕ 新增旅程天數", use_container_width=True):
            svc.add_day(trip_id)
            st.rerun()

        # Apply event filter (category/keyword)
        def event_match(e):
            kw = (f_keyword or "").strip().lower()
            if f_category and e.get("category") not in f_category:
                return False
            if kw:
                blob = " ".join([
                    str(e.get("title","")),
                    str(e.get("location","")),
                    str(e.get("notes","")),
                    str(e.get("tags","")),
                    " ".join([str(t.get("text","")) for t in e.get("tasks", [])])
                ]).lower()
                if kw not in blob:
                    return False
            return True

        for d in days:
            # 計算該天的日期
            day_date_label = ""
            if trip.get("start_date"):
                try:
                    from datetime import datetime, timedelta
                    start_date = datetime.strptime(trip["start_date"], "%Y-%m-%d")
                    current_day_date = start_date + timedelta(days=d["day_no"] - 1)
                    day_date_label = f" · {current_day_date.strftime('%Y-%m-%d')} ({['Mon','Tue','Wed','Thu','Fri','Sat','Sun'][current_day_date.weekday()]})"
                except:
                    pass
            
            day_header = st.columns([4.0, 0.6], gap="small")
            with day_header[0]:
                st.markdown(f"### Day {d['day_no']}{day_date_label}")
            with day_header[1]:
                if len(days) > 1:
                    if st.button("🗑️ 刪除", key=f"del_day_{d['day_id']}", use_container_width=True):
                        svc.delete_day(trip_id, d["day_id"])
                        st.rerun()

            st.write("")
            
            # 簡化快速新增事件區塊
            with st.container():
                st.markdown("**⚡ 快速新增事件**")
                quick_cols = st.columns(5)
                event_templates = [
                    ("✈️ 交通", "交通", "09:00"),
                    ("🏨 住宿", "住宿", "15:00"),
                    ("🍽️ 餐飲", "餐飲", "12:00"),
                    ("🎫 景點", "門票", "10:00"),
                    ("➕ 新增", "其他", "12:00")
                ]
                
                for i, (label, category, time) in enumerate(event_templates):
                    with quick_cols[i]:
                        if st.button(label, key=f"quick_add_{d['day_id']}_{category}_{i}", use_container_width=True):
                            event_id = svc.add_event(trip_id, d["day_id"])
                            svc.update_event(event_id, {"category": category, "time": time, "title": f"{category}活動" if category != "其他" else "新事件"})
                            st.rerun()

            events = [e for e in d.get("events", []) if event_match(e)]
            if not events:
                st.info("（依目前篩選器）沒有事件。")
                st.write("")
                continue

            for e in events:
                ev_title = e.get("title") or "（未命名事件）"
                ev_icon = {"交通": "✈️", "住宿": "🏨", "餐飲": "🍽️", "門票": "🎫", "購物": "🛍️", "其他": "📍"}.get(e.get('category','其他'), "📍")
                ev_cost = f" · {trip['currency']} {float(e.get('cost') or 0):,.0f}" if float(e.get('cost') or 0) > 0 else ""
                ev_sub = f"{e.get('time','')} {ev_icon} {e.get('category','其他')}{ev_cost}"
                ev_loc = f" @ {e.get('location','')}" if e.get('location','') else ""
                
                with st.expander(f"**{ev_title}**{ev_loc}  —  {ev_sub}"):
                    # 快速編輯區
                    st.markdown("##### 📝 基本資訊")
                    ec1, ec2, ec3 = st.columns([1.0, 1.0, 1.0], gap="small")
                    with ec1:
                        etime = st.text_input("⏰ 時間", value=e.get("time","12:00"), key=f"etime_{e['event_id']}", placeholder="09:00")
                    with ec2:
                        ecat = st.selectbox("🏷️ 分類", options=CATEGORIES, index=CATEGORIES.index(e.get("category","其他")) if e.get("category","其他") in CATEGORIES else CATEGORIES.index("其他"), key=f"ecat_{e['event_id']}")
                    with ec3:
                        ecost = st.number_input(f"💰 成本 ({trip['currency']})", value=float(e.get("cost") or 0), min_value=0.0, step=100.0, key=f"ecost_{e['event_id']}")

                    
                    etitle = st.text_input("📌 標題", value=e.get("title",""), key=f"etitle_{e['event_id']}", placeholder="例：午餐、飯店入住、參觀博物館")
                    eloc = st.text_input("📍 地點", value=e.get("location",""), key=f"eloc_{e['event_id']}", placeholder="例：淺草寺、東京車站")
                    
                    # 進階選項放在 expander 中
                    with st.expander("🔧 進階選項（筆記、標籤）"):
                        enotes = st.text_area("📋 筆記", value=e.get("notes",""), height=90, key=f"enotes_{e['event_id']}", 
                                            placeholder="記錄注意事項、營業時間、預訂確認碼等...")
                        etags = st.text_input("🏷️ 標籤", value=e.get("tags",""), key=f"etags_{e['event_id']}", 
                                            placeholder="逗號分隔，例：必訪,美食,拍照景點")

                    st.write("")
                    save_col1, save_col2 = st.columns([3, 1])
                    with save_col1:
                        if st.button("💾 保存事件", key=f"save_ev_{e['event_id']}", use_container_width=True, type="primary"):
                            svc.update_event(e["event_id"], {
                                "time": etime,
                                "category": ecat,
                                "cost": ecost,
                                "title": etitle,
                                "location": eloc,
                                "notes": enotes,
                                "tags": etags,
                            })
                            st.success("✅ 事件已保存！")
                            st.rerun()
                    with save_col2:
                        if st.button("🗑️ 刪除", key=f"del_ev_{e['event_id']}", use_container_width=True):
                            svc.delete_event(trip_id, e["event_id"])
                            st.rerun()

                    st.write("")
                    st.markdown("---")
                    st.markdown("##### ✅ 待辦任務")
                    st.caption("💡 為這個事件新增待辦任務，例如：訂位、買票、確認時間等")

                    # Task filters apply here too
                    def task_match(t):
                        kw = (f_keyword or "").strip().lower()
                        if f_status and t.get("status") not in f_status:
                            return False
                        if kw:
                            blob = " ".join([str(t.get("text","")), str(t.get("assignee_name",""))]).lower()
                            if kw not in blob:
                                return False
                        return True

                    tasks = [t for t in e.get("tasks", []) if task_match(t)]

                    if tasks:
                        for t in tasks:
                            tc1, tc2, tc3 = st.columns([3.0, 1.6, 0.6], gap="small")
                            with tc1:
                                ttext = st.text_input("任務內容", value=t.get("text",""), key=f"ttext_{t['task_id']}", label_visibility="collapsed")
                            with tc2:
                                # assignee
                                cur_name = "（未指派）"
                                if t.get("assignee_id") in member_map:
                                    for label, mid in member_choice_to_id.items():
                                        if mid == t.get("assignee_id"):
                                            cur_name = label
                                assignee_label = st.selectbox("指派給", options=member_choices, index=member_choices.index(cur_name), key=f"tasg_{t['task_id']}", label_visibility="collapsed")
                            with tc3:
                                if st.button("🗑️", key=f"tdel_{t['task_id']}", help="刪除", use_container_width=True):
                                    svc.delete_task(t["task_id"])
                                    st.rerun()

                            # 自動保存按鈕（當內容或指派改變時）
                            if st.button("💾 保存", key=f"tsave_{t['task_id']}", use_container_width=True):
                                # 根據任務狀態自動判斷：如果有指派人則為 doing，否則為 todo
                                task_status = "doing" if member_choice_to_id.get(assignee_label) else "todo"
                                svc.update_task(t["task_id"], {
                                    "text": ttext,
                                    "status": task_status,
                                    "assignee_id": member_choice_to_id.get(assignee_label),
                                })
                                st.rerun()
                    else:
                        st.info("（依目前篩選器）沒有任務。")

                    st.write("")
                    with st.container():
                        st.markdown("**➕ 新增任務**")
                        addt1, addt2, addt3 = st.columns([2.4, 1.4, 0.6], gap="small")
                        with addt1:
                            new_task_text = st.text_input("任務內容", value="", key=f"newtk_{e['event_id']}", 
                                                         placeholder="例如：訂餐廳、購買門票、確認交通",
                                                         label_visibility="collapsed")
                        with addt2:
                            new_task_asg = st.selectbox("指派給", options=member_choices, key=f"newtk_asg_{e['event_id']}",
                                                       label_visibility="collapsed")
                        with addt3:
                            if st.button("➕", key=f"newtk_btn_{e['event_id']}", use_container_width=True):
                                if new_task_text.strip():
                                    svc.add_task(trip_id, e["event_id"], new_task_text, member_choice_to_id.get(new_task_asg))
                                    st.rerun()
                                else:
                                    st.warning("請輸入任務內容")

            st.write("")

    with right:
        st.subheader("匯出/備份")
        export_payload = svc.export_trip_json(trip_id)
        st.download_button(
            "📤 匯出此旅程 JSON",
            data=json.dumps(export_payload, ensure_ascii=False, indent=2).encode("utf-8"),
            file_name=f"{trip['trip_title']}_export.json",
            mime="application/json",
            use_container_width=True,
        )

        st.write("")
        st.subheader("🗑️ 刪除旅程")
        if len(trips) > 1:
            with st.expander("⚠️ 危險操作", expanded=False):
                st.warning("刪除旅程將永久刪除所有相關資料（行程、任務、清單等），此操作無法復原！")
                st.caption(f"當前旅程：{trip['trip_title']} ({trip['destination']})")
                confirm_text = st.text_input("請輸入 DELETE 確認刪除", key="delete_confirm")
                if st.button("確認刪除旅程", type="secondary", use_container_width=True):
                    if confirm_text == "DELETE":
                        svc.delete_trip(trip_id)
                        st.success("✅ 旅程已刪除")
                        st.rerun()
                    else:
                        st.error("請輸入 DELETE 以確認刪除")
        else:
            st.info("這是最後一個旅程，無法刪除。請先建立新旅程。")

        st.write("")
        st.subheader("資料品質檢查")
        issues = []
        for e in all_events:
            if not (e.get("title") or "").strip():
                issues.append("存在未命名事件")
            if (e.get("category") not in CATEGORIES):
                issues.append("存在未知分類")
        if issues:
            st.warning("；".join(sorted(set(issues))))
        else:
            st.success("目前資料結構健康。")


# -----------------------
# Tab: 任務看板（全旅程）
# -----------------------
with tab_tasks:
    st.subheader("任務看板（全旅程）")

    # Flatten tasks
    rows = []
    for d in days:
        for e in d.get("events", []):
            for t in e.get("tasks", []):
                rows.append({
                    "day_no": d["day_no"],
                    "date": d.get("date") or "",
                    "category": e.get("category") or "其他",
                    "event_title": e.get("title") or "",
                    "task_id": t.get("task_id"),
                    "task": t.get("text") or "",
                    "status": t.get("status") or "todo",
                    "assignee": t.get("assignee_name") or "",
                    "assignee_id": t.get("assignee_id"),
                    "due_date": t.get("due_date") or "",
                })

    df = pd.DataFrame(rows)
    if df.empty:
        st.info("目前沒有任務。先新增事件，事件裡再加任務。")
    else:
        # apply filters
        if f_category:
            df = df[df["category"].isin(f_category)]
        if f_status:
            df = df[df["status"].isin(f_status)]
        if f_keyword.strip():
            kw = f_keyword.strip().lower()
            df = df[
                df["task"].str.lower().str.contains(kw)
                | df["event_title"].str.lower().str.contains(kw)
                | df["assignee"].str.lower().str.contains(kw)
            ]

        # extra: assignee filter in-page
        assignee_filter = st.multiselect("指派人篩選", options=sorted([a for a in df["assignee"].unique() if a] ))
        if assignee_filter:
            df = df[df["assignee"].isin(assignee_filter)]

        # show summary
        s1, s2, s3 = st.columns([1.0, 1.0, 2.0], gap="large")
        with s1:
            st.metric("任務數", len(df))
        with s2:
            st.metric("完成率", f"{round((df['status'].eq('done').sum()/len(df))*100)}%" if len(df) else "0%")
        with s3:
            st.caption("小技巧：點任務所在事件去編輯指派/狀態；這裡是『監控台』。")

        st.dataframe(
            df.sort_values(["status", "day_no", "due_date"], ascending=[True, True, True]),
            use_container_width=True,
            hide_index=True,
        )


# -----------------------
# Tab: 團隊管理
# -----------------------
with tab_team:
    st.subheader("旅遊團隊管理")

    # Create member
    with st.expander("➕ 新增人員", expanded=False):
        nm = st.text_input("姓名", value="")
        nr = st.text_input("角色/職責（例：交通、訂房、攝影）", value="")
        ne = st.text_input("Email（可選）", value="")
        if st.button("建立成員", use_container_width=True):
            try:
                mid = svc.create_member(nm, nr, ne)
                svc.add_member_to_trip(trip_id, mid)
                st.success("已新增並加入此旅程。")
                st.rerun()
            except Exception as e:
                st.error(str(e))

    st.write("")

    # List members in this trip
    if not members:
        st.info("此旅程目前沒有團隊成員。可以先新增人員。")
    else:
        for m in members:
            mc1, mc2, mc3, mc4 = st.columns([1.4, 1.2, 1.8, 0.6], gap="small")
            with mc1:
                st.write(f"**{m['name']}**")
                st.caption(m.get("role","") or "")
            with mc2:
                st.write(m.get("email","") or "")
            with mc3:
                # quick stats: assigned tasks count
                assigned = 0
                done = 0
                for d in days:
                    for e in d.get("events", []):
                        for t in e.get("tasks", []):
                            if t.get("assignee_id") == m["member_id"]:
                                assigned += 1
                                if t.get("status") == "done":
                                    done += 1
                st.write(f"指派任務：{done}/{assigned} 完成")
            with mc4:
                if st.button("移出旅程", key=f"rm_{m['member_id']}", use_container_width=True):
                    svc.remove_member_from_trip(trip_id, m["member_id"])
                    st.rerun()

    st.write("")
    st.markdown("---")
    st.subheader("把既有人員加入此旅程")
    all_members = svc.list_all_members(active_only=True)
    # filter those not in trip already
    in_trip_ids = set([m["member_id"] for m in members])
    candidates = [m for m in all_members if m["member_id"] not in in_trip_ids]

    if not candidates:
        st.caption("沒有可加入的既有人員（或都已在旅程中）。")
    else:
        pick = st.selectbox("選擇成員", options=[f"{m['name']} ({m.get('role','')})".strip() for m in candidates])
        pick_id = None
        for m in candidates:
            if pick.startswith(m["name"]):
                pick_id = m["member_id"]
                break
        if st.button("加入旅程", use_container_width=True):
            if pick_id:
                svc.add_member_to_trip(trip_id, pick_id)
                st.rerun()


# -----------------------
# Tab: 準備清單
# -----------------------
with tab_check:
    st.subheader("準備清單（可自訂多清單）")

    # Create new checklist
    with st.expander("➕ 新增清單", expanded=False):
        lk = st.text_input("list_key（documents/packing/custom...）", value="custom")
        title = st.text_input("清單標題", value="新清單")
        if st.button("建立清單", use_container_width=True):
            svc.add_checklist(trip_id, lk.strip() or "custom", title.strip() or "新清單")
            st.rerun()

    st.write("")

    for cl in checklists:
        st.markdown(f"### {cl['title']}  ·  ({cl['list_key']})")
        cdel = st.columns([0.8, 2.2], gap="small")
        with cdel[0]:
            if st.button("刪除清單", key=f"delcl_{cl['checklist_id']}", use_container_width=True):
                svc.delete_checklist(cl["checklist_id"])
                st.rerun()
        with cdel[1]:
            st.caption("點勾選即可完成；項目文字可直接編輯。")

        items = cl.get("items", [])
        if not items:
            st.info("清單是空的。加幾個項目吧。")
        else:
            for it in items:
                ic1, ic2, ic3 = st.columns([0.12, 2.4, 0.5], gap="small")
                with ic1:
                    chk = st.checkbox("", value=bool(it.get("checked")), key=f"chk_{it['item_id']}")
                with ic2:
                    txt = st.text_input("項目", value=it.get("text",""), key=f"txt_{it['item_id']}", label_visibility="collapsed")
                with ic3:
                    if st.button("🗑️", key=f"delit_{it['item_id']}", use_container_width=True):
                        svc.delete_checklist_item(it["item_id"])
                        st.rerun()

                if st.button("保存項目", key=f"saveit_{it['item_id']}", use_container_width=True):
                    svc.update_checklist_item(it["item_id"], {"text": txt, "checked": chk})
                    st.rerun()

        st.write("")
        addi1, addi2 = st.columns([2.4, 0.6], gap="small")
        with addi1:
            new_item = st.text_input("新增項目", value="", key=f"new_item_{cl['checklist_id']}")
        with addi2:
            if st.button("新增", key=f"btn_add_item_{cl['checklist_id']}", use_container_width=True):
                svc.add_checklist_item(cl["checklist_id"], new_item)
                st.rerun()

        st.divider()
