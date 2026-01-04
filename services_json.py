import json
import uuid
from datetime import datetime
from dateutil.parser import parse as dtparse

import json_storage as storage
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
    """返回單一旅程的列表形式（為了兼容原有接口）"""
    trip = storage.get_trip()
    return [trip] if trip else []


def create_trip(data: dict | None = None) -> str:
    """創建/初始化旅程"""
    d = {**DEFAULT_TRIP, **(data or {})}
    trip_id = "trip_default"
    
    trip_data = {
        "trip_id": trip_id,
        "trip_title": d.get("tripTitle", "韓國釜山行"),
        "destination": d.get("destination", "釜山"),
        "start_date": safe_date_str(d.get("startDate", "")),
        "end_date": safe_date_str(d.get("endDate", "")),
        "currency": d.get("currency", "KRW"),
        "created_at": now_iso(),
    }
    
    storage.update_trip(trip_data)
    
    # 初始化第一天
    if not storage.get_days():
        day_id = uid("day")
        storage.add_day({
            "day_id": day_id,
            "day_no": 1,
            "date": safe_date_str(d.get("startDate", "")),
            "note": "",
            "created_at": now_iso()
        })
    
    return trip_id


def get_trip(trip_id: str) -> dict:
    """獲取旅程及所有相關數據"""
    trip = storage.get_trip()
    days_list = storage.get_days()
    
    # 為每一天加載事件和任務
    for day in days_list:
        day["events"] = storage.get_events_by_day(day["day_id"])
        # 為每個事件加載任務
        for event in day["events"]:
            event["tasks"] = [t for t in storage.get_tasks() if t.get("event_id") == event["event_id"]]
    
    return {
        "trip": trip,
        "days": days_list,
        "members": storage.get_members(),
        "checklists": storage.get_checklists()
    }


def update_trip(trip_id: str, data: dict):
    """更新旅程信息"""
    updates = {}
    if "trip_title" in data:
        updates["trip_title"] = data["trip_title"]
    if "destination" in data:
        updates["destination"] = data["destination"]
    if "start_date" in data:
        updates["start_date"] = safe_date_str(data["start_date"])
    if "end_date" in data:
        updates["end_date"] = safe_date_str(data["end_date"])
    if "currency" in data:
        updates["currency"] = data["currency"]
    
    storage.update_trip(updates)


def delete_trip(trip_id: str):
    """清空旅程數據（保留結構）"""
    # 重置為默認數據
    from json_storage import DEFAULT_DATA
    storage.save_data(DEFAULT_DATA.copy())


# -----------------------
# Days
# -----------------------
def add_day(trip_id: str, day_no: int, date_str: str = "") -> str:
    day_id = uid("day")
    storage.add_day({
        "day_id": day_id,
        "day_no": day_no,
        "date": safe_date_str(date_str),
        "note": "",
        "created_at": now_iso()
    })
    return day_id


def update_day(day_id: str, data: dict):
    updates = {}
    if "date" in data:
        updates["date"] = safe_date_str(data["date"])
    if "note" in data:
        updates["note"] = data["note"]
    storage.update_day(day_id, updates)


def delete_day(day_id: str):
    storage.delete_day(day_id)


# -----------------------
# Events
# -----------------------
def add_event(day_id: str, data: dict) -> str:
    event_id = uid("evt")
    storage.add_event({
        "event_id": event_id,
        "day_id": day_id,
        "event_title": data.get("eventTitle", ""),
        "category": data.get("category", "其他"),
        "time_slot": data.get("timeSlot", ""),
        "location": data.get("location", ""),
        "cost": float(data.get("cost", 0)),
        "note": data.get("note", ""),
        "created_at": now_iso()
    })
    return event_id


def update_event(event_id: str, data: dict):
    updates = {}
    if "eventTitle" in data:
        updates["event_title"] = data["eventTitle"]
    if "category" in data:
        updates["category"] = data["category"]
    if "timeSlot" in data:
        updates["time_slot"] = data["timeSlot"]
    if "location" in data:
        updates["location"] = data["location"]
    if "cost" in data:
        updates["cost"] = float(data["cost"])
    if "note" in data:
        updates["note"] = data["note"]
    
    storage.update_event(event_id, updates)


def delete_event(event_id: str):
    # 先刪除相關任務
    tasks = storage.get_tasks()
    for task in tasks:
        if task.get("event_id") == event_id:
            storage.delete_task(task["task_id"])
    # 刪除事件
    storage.delete_event(event_id)


# -----------------------
# Members
# -----------------------
def add_member(trip_id: str, data: dict) -> str:
    member_id = uid("mem")
    storage.add_member({
        "member_id": member_id,
        "name": data.get("name", ""),
        "role": data.get("role", ""),
        "contact": data.get("contact", ""),
        "created_at": now_iso()
    })
    return member_id


def update_member(member_id: str, data: dict):
    updates = {}
    if "name" in data:
        updates["name"] = data["name"]
    if "role" in data:
        updates["role"] = data["role"]
    if "contact" in data:
        updates["contact"] = data["contact"]
    
    storage.update_member(member_id, updates)


def delete_member(member_id: str):
    storage.delete_member(member_id)


# -----------------------
# Tasks
# -----------------------
def add_task(trip_id: str, data: dict) -> str:
    task_id = uid("task")
    storage.add_task({
        "task_id": task_id,
        "event_id": data.get("eventId"),
        "day_id": data.get("dayId"),
        "content": data.get("content", ""),
        "assignee_id": data.get("assigneeId"),
        "status": data.get("status", "todo"),
        "completed": data.get("completed", False),
        "created_at": now_iso()
    })
    return task_id


def update_task(task_id: str, data: dict):
    updates = {}
    if "content" in data:
        updates["content"] = data["content"]
    if "assigneeId" in data:
        updates["assignee_id"] = data["assigneeId"]
    if "status" in data:
        updates["status"] = data["status"]
    if "completed" in data:
        updates["completed"] = data["completed"]
    
    storage.update_task(task_id, updates)


def delete_task(task_id: str):
    storage.delete_task(task_id)


# -----------------------
# Checklists
# -----------------------
def add_checklist_item(checklist_id: str, data: dict) -> str:
    item_id = uid("item")
    storage.add_checklist_item(checklist_id, {
        "item_id": item_id,
        "content": data.get("content", ""),
        "checked": data.get("checked", False),
        "created_at": now_iso()
    })
    return item_id


def update_checklist_item(item_id: str, data: dict):
    updates = {}
    if "content" in data:
        updates["content"] = data["content"]
    if "checked" in data:
        updates["checked"] = data["checked"]
    
    storage.update_checklist_item(item_id, updates)


def delete_checklist_item(item_id: str):
    storage.delete_checklist_item(item_id)


# -----------------------
# Export / Import
# -----------------------
def export_all_trips():
    """匯出所有數據"""
    return storage.export_to_json()


def import_trip_data(json_str: str) -> bool:
    """導入數據"""
    return storage.import_from_json(json_str)
