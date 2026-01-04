import json
import uuid
from datetime import datetime
from dateutil.parser import parse as dtparse

from db import get_conn
from modals import DEFAULT_TRIP, CATEGORIES, TASK_STATUS


def now_iso():
    return datetime.utcnow().isoformat(timespec="seconds")


def uid(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex}"


def safe_date_str(s: str) -> str:
    if not s:
        return ""
    try:
        return dtparse(str(s)).date().isoformat()
    except Exception:
        return ""


# -----------------------
# Trip
# -----------------------
def list_trips():
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM trips ORDER BY created_at DESC"
        ).fetchall()
        return [dict(r) for r in rows]


def create_trip(data: dict | None = None) -> str:
    d = {**DEFAULT_TRIP, **(data or {})}
    trip_id = uid("trip")
    with get_conn() as conn:
        conn.execute(
            """INSERT INTO trips(trip_id, trip_title, destination, start_date, end_date, currency, created_at)
               VALUES(?,?,?,?,?,?,?)""",
            (
                trip_id,
                d["tripTitle"],
                d["destination"],
                safe_date_str(d.get("startDate", "")),
                safe_date_str(d.get("endDate", "")),
                d["currency"],
                now_iso(),
            ),
        )
        # default checklists
        cl_docs = uid("cl")
        cl_pack = uid("cl")
        conn.execute(
            "INSERT INTO checklists(checklist_id, trip_id, list_key, title, created_at) VALUES(?,?,?,?,?)",
            (cl_docs, trip_id, "documents", "必備文件與證件", now_iso()),
        )
        conn.execute(
            "INSERT INTO checklists(checklist_id, trip_id, list_key, title, created_at) VALUES(?,?,?,?,?)",
            (cl_pack, trip_id, "packing", "行李打包清單", now_iso()),
        )

        # default day 1
        day_id = uid("day")
        conn.execute(
            "INSERT INTO days(day_id, trip_id, day_no, date, note, created_at) VALUES(?,?,?,?,?,?)",
            (day_id, trip_id, 1, safe_date_str(d.get("startDate", "")), "", now_iso()),
        )
        conn.commit()
    return trip_id


def delete_trip(trip_id: str):
    """Delete a trip and all related data"""
    with get_conn() as conn:
        # Delete in order due to foreign key constraints
        conn.execute("DELETE FROM checklist_items WHERE checklist_id IN (SELECT checklist_id FROM checklists WHERE trip_id=?)", (trip_id,))
        conn.execute("DELETE FROM checklists WHERE trip_id=?", (trip_id,))
        conn.execute("DELETE FROM tasks WHERE trip_id=?", (trip_id,))
        conn.execute("DELETE FROM events WHERE trip_id=?", (trip_id,))
        conn.execute("DELETE FROM days WHERE trip_id=?", (trip_id,))
        conn.execute("DELETE FROM trip_members WHERE trip_id=?", (trip_id,))
        conn.execute("DELETE FROM trips WHERE trip_id=?", (trip_id,))
        conn.commit()


def get_trip(trip_id: str) -> dict:
    with get_conn() as conn:
        t = conn.execute("SELECT * FROM trips WHERE trip_id=?", (trip_id,)).fetchone()
        if not t:
            raise ValueError("Trip not found")

        days = conn.execute(
            "SELECT * FROM days WHERE trip_id=? ORDER BY day_no ASC", (trip_id,)
        ).fetchall()

        events = conn.execute(
            "SELECT * FROM events WHERE trip_id=? ORDER BY day_id, time ASC", (trip_id,)
        ).fetchall()

        tasks = conn.execute(
            """SELECT tk.*, m.name as assignee_name
               FROM tasks tk
               LEFT JOIN members m ON m.member_id = tk.assignee_id
               WHERE tk.trip_id=?""",
            (trip_id,),
        ).fetchall()

        checklists = conn.execute(
            "SELECT * FROM checklists WHERE trip_id=? ORDER BY created_at ASC", (trip_id,)
        ).fetchall()

        checklist_items = conn.execute(
            """SELECT i.*, c.list_key
               FROM checklist_items i
               JOIN checklists c ON c.checklist_id=i.checklist_id
               WHERE c.trip_id=?""",
            (trip_id,),
        ).fetchall()

        members = conn.execute(
            """SELECT m.* FROM members m
               JOIN trip_members tm ON tm.member_id=m.member_id
               WHERE tm.trip_id=? AND m.active=1
               ORDER BY m.created_at ASC""",
            (trip_id,),
        ).fetchall()

    # assemble
    day_map = {d["day_id"]: dict(d) for d in days}
    for d in day_map.values():
        d["events"] = []

    event_map = {}
    for e in events:
        ed = dict(e)
        ed["tasks"] = []
        event_map[ed["event_id"]] = ed
        day_map[ed["day_id"]]["events"].append(ed)

    for tk in tasks:
        tdd = dict(tk)
        if tdd["status"] not in TASK_STATUS:
            tdd["status"] = "todo"
        if tdd["event_id"] in event_map:
            event_map[tdd["event_id"]]["tasks"].append(tdd)

    cl_map = {c["checklist_id"]: dict(c) for c in checklists}
    for c in cl_map.values():
        c["items"] = []

    for it in checklist_items:
        it = dict(it)
        cid = it["checklist_id"]
        if cid in cl_map:
            cl_map[cid]["items"].append(it)

    return {
        "trip": dict(t),
        "days": list(day_map.values()),
        "checklists": list(cl_map.values()),
        "members": [dict(m) for m in members],
    }


def update_trip(trip_id: str, fields: dict):
    allowed = {
        "trip_title", "destination", "start_date", "end_date", "currency"
    }
    sets = []
    vals = []
    for k, v in fields.items():
        if k not in allowed:
            continue
        if k in ("start_date", "end_date"):
            v = safe_date_str(v)
        sets.append(f"{k}=?")
        vals.append(v)
    if not sets:
        return
    vals.append(trip_id)
    with get_conn() as conn:
        conn.execute(f"UPDATE trips SET {', '.join(sets)} WHERE trip_id=?", vals)
        conn.commit()


# -----------------------
# Days
# -----------------------
def add_day(trip_id: str) -> str:
    with get_conn() as conn:
        r = conn.execute("SELECT COALESCE(MAX(day_no),0) as mx FROM days WHERE trip_id=?", (trip_id,)).fetchone()
        next_no = int(r["mx"]) + 1
        day_id = uid("day")
        conn.execute(
            "INSERT INTO days(day_id, trip_id, day_no, date, note, created_at) VALUES(?,?,?,?,?,?)",
            (day_id, trip_id, next_no, "", "", now_iso()),
        )
        conn.commit()
    return day_id


def delete_day(trip_id: str, day_id: str):
    # cascade manually: delete tasks -> events -> day
    with get_conn() as conn:
        evs = conn.execute("SELECT event_id FROM events WHERE day_id=? AND trip_id=?", (day_id, trip_id)).fetchall()
        ev_ids = [e["event_id"] for e in evs]
        if ev_ids:
            q = ",".join(["?"] * len(ev_ids))
            conn.execute(f"DELETE FROM tasks WHERE trip_id=? AND event_id IN ({q})", [trip_id, *ev_ids])
            conn.execute(f"DELETE FROM events WHERE trip_id=? AND day_id=?", (trip_id, day_id))
        conn.execute("DELETE FROM days WHERE trip_id=? AND day_id=?", (trip_id, day_id))
        # re-number day_no
        rows = conn.execute("SELECT day_id FROM days WHERE trip_id=? ORDER BY day_no ASC", (trip_id,)).fetchall()
        for i, r in enumerate(rows, start=1):
            conn.execute("UPDATE days SET day_no=? WHERE day_id=?", (i, r["day_id"]))
        conn.commit()


def update_day(day_id: str, fields: dict):
    allowed = {"date", "note"}
    sets, vals = [], []
    for k, v in fields.items():
        if k not in allowed:
            continue
        if k == "date":
            v = safe_date_str(v)
        sets.append(f"{k}=?")
        vals.append(v)
    if not sets:
        return
    vals.append(day_id)
    with get_conn() as conn:
        conn.execute(f"UPDATE days SET {', '.join(sets)} WHERE day_id=?", vals)
        conn.commit()


# -----------------------
# Events
# -----------------------
def add_event(trip_id: str, day_id: str) -> str:
    event_id = uid("ev")
    with get_conn() as conn:
        conn.execute(
            """INSERT INTO events(event_id, trip_id, day_id, time, title, location, category, cost, notes, tags, created_at)
               VALUES(?,?,?,?,?,?,?,?,?,?,?)""",
            (event_id, trip_id, day_id, "12:00", "", "", "其他", 0.0, "", "", now_iso()),
        )
        conn.commit()
    return event_id


def delete_event(trip_id: str, event_id: str):
    with get_conn() as conn:
        conn.execute("DELETE FROM tasks WHERE trip_id=? AND event_id=?", (trip_id, event_id))
        conn.execute("DELETE FROM events WHERE trip_id=? AND event_id=?", (trip_id, event_id))
        conn.commit()


def update_event(event_id: str, fields: dict):
    allowed = {"time", "title", "location", "category", "cost", "notes", "tags"}
    sets, vals = [], []
    for k, v in fields.items():
        if k not in allowed:
            continue
        if k == "category" and v not in CATEGORIES:
            v = "其他"
        if k == "cost":
            try:
                v = float(v or 0)
            except Exception:
                v = 0.0
        sets.append(f"{k}=?")
        vals.append(v)
    if not sets:
        return
    vals.append(event_id)
    with get_conn() as conn:
        conn.execute(f"UPDATE events SET {', '.join(sets)} WHERE event_id=?", vals)
        conn.commit()


# -----------------------
# Tasks (assignable)
# -----------------------
def add_task(trip_id: str, event_id: str, text: str, assignee_id: str | None = None):
    if not text.strip():
        return
    task_id = uid("tk")
    with get_conn() as conn:
        conn.execute(
            """INSERT INTO tasks(task_id, trip_id, event_id, text, status, assignee_id, due_date, priority, created_at)
               VALUES(?,?,?,?,?,?,?,?,?)""",
            (task_id, trip_id, event_id, text.strip(), "todo", assignee_id, "", 3, now_iso()),
        )
        conn.commit()


def update_task(task_id: str, fields: dict):
    allowed = {"text", "status", "assignee_id", "due_date", "priority"}
    sets, vals = [], []
    for k, v in fields.items():
        if k not in allowed:
            continue
        if k == "status" and v not in TASK_STATUS:
            v = "todo"
        if k == "due_date":
            v = safe_date_str(v)
        if k == "priority":
            try:
                v = int(v)
                v = max(1, min(5, v))
            except Exception:
                v = 3
        sets.append(f"{k}=?")
        vals.append(v)
    if not sets:
        return
    vals.append(task_id)
    with get_conn() as conn:
        conn.execute(f"UPDATE tasks SET {', '.join(sets)} WHERE task_id=?", vals)
        conn.commit()


def delete_task(task_id: str):
    with get_conn() as conn:
        conn.execute("DELETE FROM tasks WHERE task_id=?", (task_id,))
        conn.commit()


# -----------------------
# Members & Assignment
# -----------------------
def list_all_members(active_only=True):
    with get_conn() as conn:
        if active_only:
            rows = conn.execute("SELECT * FROM members WHERE active=1 ORDER BY created_at ASC").fetchall()
        else:
            rows = conn.execute("SELECT * FROM members ORDER BY created_at ASC").fetchall()
        return [dict(r) for r in rows]


def create_member(name: str, role: str = "", email: str = "") -> str:
    if not name.strip():
        raise ValueError("name required")
    mid = uid("mem")
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO members(member_id, name, role, email, active, created_at) VALUES(?,?,?,?,?,?)",
            (mid, name.strip(), role.strip(), email.strip(), 1, now_iso()),
        )
        conn.commit()
    return mid


def set_member_active(member_id: str, active: bool):
    with get_conn() as conn:
        conn.execute("UPDATE members SET active=? WHERE member_id=?", (1 if active else 0, member_id))
        conn.commit()


def add_member_to_trip(trip_id: str, member_id: str):
    with get_conn() as conn:
        conn.execute(
            "INSERT OR IGNORE INTO trip_members(trip_id, member_id) VALUES(?,?)",
            (trip_id, member_id),
        )
        conn.commit()


def remove_member_from_trip(trip_id: str, member_id: str):
    with get_conn() as conn:
        conn.execute("DELETE FROM trip_members WHERE trip_id=? AND member_id=?", (trip_id, member_id))
        # also unassign tasks
        conn.execute("UPDATE tasks SET assignee_id=NULL WHERE trip_id=? AND assignee_id=?", (trip_id, member_id))
        conn.commit()


# -----------------------
# Checklists
# -----------------------
def list_checklists(trip_id: str):
    with get_conn() as conn:
        rows = conn.execute("SELECT * FROM checklists WHERE trip_id=? ORDER BY created_at ASC", (trip_id,)).fetchall()
        return [dict(r) for r in rows]


def add_checklist(trip_id: str, list_key: str, title: str) -> str:
    cid = uid("cl")
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO checklists(checklist_id, trip_id, list_key, title, created_at) VALUES(?,?,?,?,?)",
            (cid, trip_id, list_key, title.strip() or "新清單", now_iso()),
        )
        conn.commit()
    return cid


def delete_checklist(checklist_id: str):
    with get_conn() as conn:
        conn.execute("DELETE FROM checklist_items WHERE checklist_id=?", (checklist_id,))
        conn.execute("DELETE FROM checklists WHERE checklist_id=?", (checklist_id,))
        conn.commit()


def add_checklist_item(checklist_id: str, text: str):
    if not text.strip():
        return
    iid = uid("it")
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO checklist_items(item_id, checklist_id, text, checked, created_at) VALUES(?,?,?,?,?)",
            (iid, checklist_id, text.strip(), 0, now_iso()),
        )
        conn.commit()


def update_checklist_item(item_id: str, fields: dict):
    allowed = {"text", "checked"}
    sets, vals = [], []
    for k, v in fields.items():
        if k not in allowed:
            continue
        if k == "checked":
            v = 1 if bool(v) else 0
        sets.append(f"{k}=?")
        vals.append(v)
    if not sets:
        return
    vals.append(item_id)
    with get_conn() as conn:
        conn.execute(f"UPDATE checklist_items SET {', '.join(sets)} WHERE item_id=?", vals)
        conn.commit()


def delete_checklist_item(item_id: str):
    with get_conn() as conn:
        conn.execute("DELETE FROM checklist_items WHERE item_id=?", (item_id,))
        conn.commit()


# -----------------------
# Export / Import JSON
# -----------------------
def export_trip_json(trip_id: str) -> dict:
    bundle = get_trip(trip_id)

    # normalize to a portable JSON
    return {
        "trip": bundle["trip"],
        "days": bundle["days"],
        "checklists": bundle["checklists"],
        "members": bundle["members"],
    }


def import_trip_json(payload: dict) -> str:
    """
    匯入策略：
    - 直接建立一個新 trip（避免覆蓋舊資料造成不可逆）
    - 成員：以 email+name 做弱匹配，不存在就新增
    - day/event/task/checklist 全部建立新 ID
    """
    if not isinstance(payload, dict) or "trip" not in payload:
        raise ValueError("Invalid JSON structure")

    trip_info = payload["trip"] or {}
    new_trip_id = create_trip({
        "tripTitle": trip_info.get("trip_title", trip_info.get("tripTitle", DEFAULT_TRIP["tripTitle"])),
        "destination": trip_info.get("destination", DEFAULT_TRIP["destination"]),
        "startDate": trip_info.get("start_date", trip_info.get("startDate", "")),
        "endDate": trip_info.get("end_date", trip_info.get("endDate", "")),
        "currency": trip_info.get("currency", DEFAULT_TRIP["currency"]),
    })

    # members
    imported_members = payload.get("members", []) or []
    # create mapping old_member_id -> new_member_id
    member_map = {}

    existing = list_all_members(active_only=False)
    def find_member(name, email):
        for m in existing:
            if email and m.get("email","").lower() == email.lower():
                return m["member_id"]
        for m in existing:
            if (m.get("name","") == name) and name:
                return m["member_id"]
        return None

    for m in imported_members:
        name = (m.get("name") or "").strip()
        email = (m.get("email") or "").strip()
        role = (m.get("role") or "").strip()
        if not name:
            continue
        mid = find_member(name, email)
        if not mid:
            mid = create_member(name=name, role=role, email=email)
            existing = list_all_members(active_only=False)
        add_member_to_trip(new_trip_id, mid)
        old_id = m.get("member_id")
        if old_id:
            member_map[old_id] = mid

    # wipe default day1 and default checklists created by create_trip
    # We'll keep them but overwrite by adding imported; that’s fine.
    # Days/events/tasks
    imported_days = payload.get("days", []) or []
    for d in imported_days:
        day_no = int(d.get("day_no", d.get("day_no", d.get("day", 1))) or 1)
        # ensure day exists with that day_no (create if needed)
        # create missing days until reach day_no
        with get_conn() as conn:
            r = conn.execute("SELECT COALESCE(MAX(day_no),0) mx FROM days WHERE trip_id=?", (new_trip_id,)).fetchone()
            mx = int(r["mx"])
        while mx < day_no:
            add_day(new_trip_id)
            mx += 1

        # get day_id by trip_id+day_no
        with get_conn() as conn:
            row = conn.execute("SELECT day_id FROM days WHERE trip_id=? AND day_no=?", (new_trip_id, day_no)).fetchone()
            day_id = row["day_id"]

        update_day(day_id, {"date": d.get("date",""), "note": d.get("note","")})

        for ev in d.get("events", []) or []:
            ev_id = add_event(new_trip_id, day_id)
            update_event(ev_id, {
                "time": ev.get("time","12:00"),
                "title": ev.get("title",""),
                "location": ev.get("location",""),
                "category": ev.get("category","其他"),
                "cost": ev.get("cost", 0),
                "notes": ev.get("notes",""),
                "tags": ev.get("tags",""),
            })
            for tk in ev.get("tasks", []) or []:
                # create task
                assignee_old = tk.get("assignee_id")
                assignee_new = member_map.get(assignee_old) if assignee_old else None
                add_task(new_trip_id, ev_id, tk.get("text",""), assignee_new)

    # checklists
    imported_cls = payload.get("checklists", []) or []
    for c in imported_cls:
        list_key = c.get("list_key") or c.get("key") or "custom"
        title = c.get("title") or "匯入清單"
        cid = add_checklist(new_trip_id, list_key, title)
        for it in c.get("items", []) or []:
            add_checklist_item(cid, it.get("text",""))
            # set checked on last inserted item: easiest is update by selecting newest item
            if it.get("checked"):
                with get_conn() as conn:
                    row = conn.execute(
                        "SELECT item_id FROM checklist_items WHERE checklist_id=? ORDER BY created_at DESC LIMIT 1",
                        (cid,)
                    ).fetchone()
                    if row:
                        update_checklist_item(row["item_id"], {"checked": True})

    return new_trip_id
