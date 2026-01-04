import json
import os
from pathlib import Path
from typing import Any

# JSON 文件路徑
DATA_FILE = Path(__file__).parent / "travel_data.json"

# 默認數據結構
DEFAULT_DATA = {
    "trip": {
        "trip_id": "trip_default",
        "trip_title": "韓國釜山行",
        "destination": "釜山",
        "start_date": "",
        "end_date": "",
        "currency": "KRW",
        "created_at": ""
    },
    "days": [],
    "members": [],
    "events": [],
    "tasks": [],
    "checklists": [
        {
            "checklist_id": "cl_docs",
            "list_key": "documents",
            "title": "必備文件與證件",
            "items": [],
            "created_at": ""
        },
        {
            "checklist_id": "cl_pack",
            "list_key": "packing",
            "title": "行李打包清單",
            "items": [],
            "created_at": ""
        }
    ]
}


def load_data() -> dict:
    """從 JSON 文件載入數據"""
    if not DATA_FILE.exists():
        save_data(DEFAULT_DATA)
        return DEFAULT_DATA.copy()
    
    try:
        with open(DATA_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        # 如果文件損壞，返回默認數據
        return DEFAULT_DATA.copy()


def save_data(data: dict) -> None:
    """保存數據到 JSON 文件"""
    with open(DATA_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def get_data() -> dict:
    """獲取當前數據（包裝函數）"""
    return load_data()


def update_trip(updates: dict) -> None:
    """更新旅程信息"""
    data = load_data()
    data["trip"].update(updates)
    save_data(data)


def get_trip() -> dict:
    """獲取旅程信息"""
    data = load_data()
    return data["trip"]


# Days
def add_day(day: dict) -> None:
    """新增一天"""
    data = load_data()
    data["days"].append(day)
    save_data(data)


def update_day(day_id: str, updates: dict) -> None:
    """更新某一天的資訊"""
    data = load_data()
    for day in data["days"]:
        if day["day_id"] == day_id:
            day.update(updates)
            break
    save_data(data)


def delete_day(day_id: str) -> None:
    """刪除某一天及其所有事件和任務"""
    data = load_data()
    # 刪除該天的所有事件
    data["events"] = [e for e in data["events"] if e["day_id"] != day_id]
    # 刪除該天的所有任務
    data["tasks"] = [t for t in data["tasks"] if t.get("day_id") != day_id]
    # 刪除該天
    data["days"] = [d for d in data["days"] if d["day_id"] != day_id]
    save_data(data)


def get_days() -> list:
    """獲取所有天數"""
    data = load_data()
    return sorted(data["days"], key=lambda x: x.get("day_no", 0))


# Events
def add_event(event: dict) -> None:
    """新增事件"""
    data = load_data()
    data["events"].append(event)
    save_data(data)


def update_event(event_id: str, updates: dict) -> None:
    """更新事件"""
    data = load_data()
    for event in data["events"]:
        if event["event_id"] == event_id:
            event.update(updates)
            break
    save_data(data)


def delete_event(event_id: str) -> None:
    """刪除事件"""
    data = load_data()
    data["events"] = [e for e in data["events"] if e["event_id"] != event_id]
    save_data(data)


def get_events_by_day(day_id: str) -> list:
    """獲取某天的所有事件"""
    data = load_data()
    return [e for e in data["events"] if e["day_id"] == day_id]


# Members
def add_member(member: dict) -> None:
    """新增成員"""
    data = load_data()
    data["members"].append(member)
    save_data(data)


def update_member(member_id: str, updates: dict) -> None:
    """更新成員"""
    data = load_data()
    for member in data["members"]:
        if member["member_id"] == member_id:
            member.update(updates)
            break
    save_data(data)


def delete_member(member_id: str) -> None:
    """刪除成員，並將其任務設為未指派"""
    data = load_data()
    data["members"] = [m for m in data["members"] if m["member_id"] != member_id]
    # 將該成員的任務設為未指派
    for task in data["tasks"]:
        if task.get("assignee_id") == member_id:
            task["assignee_id"] = None
    save_data(data)


def get_members() -> list:
    """獲取所有成員"""
    data = load_data()
    return data["members"]


# Tasks
def add_task(task: dict) -> None:
    """新增任務"""
    data = load_data()
    data["tasks"].append(task)
    save_data(data)


def update_task(task_id: str, updates: dict) -> None:
    """更新任務"""
    data = load_data()
    for task in data["tasks"]:
        if task["task_id"] == task_id:
            task.update(updates)
            break
    save_data(data)


def delete_task(task_id: str) -> None:
    """刪除任務"""
    data = load_data()
    data["tasks"] = [t for t in data["tasks"] if t["task_id"] != task_id]
    save_data(data)


def get_tasks() -> list:
    """獲取所有任務"""
    data = load_data()
    return data["tasks"]


# Checklists
def add_checklist_item(checklist_id: str, item: dict) -> None:
    """新增檢查清單項目"""
    data = load_data()
    for checklist in data["checklists"]:
        if checklist["checklist_id"] == checklist_id:
            if "items" not in checklist:
                checklist["items"] = []
            checklist["items"].append(item)
            break
    save_data(data)


def update_checklist_item(item_id: str, updates: dict) -> None:
    """更新檢查清單項目"""
    data = load_data()
    for checklist in data["checklists"]:
        for item in checklist.get("items", []):
            if item["item_id"] == item_id:
                item.update(updates)
                save_data(data)
                return


def delete_checklist_item(item_id: str) -> None:
    """刪除檢查清單項目"""
    data = load_data()
    for checklist in data["checklists"]:
        if "items" in checklist:
            checklist["items"] = [i for i in checklist["items"] if i["item_id"] != item_id]
    save_data(data)


def get_checklists() -> list:
    """獲取所有檢查清單"""
    data = load_data()
    return data["checklists"]


# Export/Import
def export_to_json() -> str:
    """匯出數據為 JSON 字符串"""
    data = load_data()
    return json.dumps(data, ensure_ascii=False, indent=2)


def import_from_json(json_str: str) -> bool:
    """從 JSON 字符串導入數據"""
    try:
        data = json.loads(json_str)
        save_data(data)
        return True
    except json.JSONDecodeError:
        return False
