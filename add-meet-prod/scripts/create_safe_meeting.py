#!/usr/bin/env python3
"""Create a 263 safe meeting and add requested people through captured HTTP APIs."""

import argparse
import datetime as dt
import json
import os
import re
import ssl
import sys
import urllib.parse
import urllib.request
from http.cookiejar import CookieJar
from typing import Any, Dict, List, Optional, Tuple


DEFAULT_BASE_URL = "https://sec.263.net"
DEFAULT_USERNAME = "lvchen01@rabyte.cn"
DEFAULT_PASSWORD_HASH = "8EC74602A69590199839C5D63A2BD7E9FA3AF6C957EE616D"
DEFAULT_HOST_NUMBER = "18000000001"
DEFAULT_HOST_EMAIL = "123@qq.com"
DEFAULT_HOSTS_JSON = '[{"name":"杨欣","phone":"17600215916"}]'
DEFAULT_GUESTS_JSON = '[{"name":"测试观众","phone":"13772400120","company":"测试观众组织"}]'
WHITE_LIST_VALID_RANGES = {
    "open": "buyerOpen,platformOpen,orgWhiteList,calloutList,specialList",
    "limited": "calloutList,specialList",
    "public": "buyerOpen,platformOpen,orgWhiteList,calloutList,specialList",
    "private": "calloutList,specialList",
}
MEETING_TYPE_LABELS = {
    "open": "公开会议",
    "limited": "小范围会议",
    "public": "公开会议",
    "private": "小范围会议",
}


class SafeMeetingClient:
    def __init__(self, base_url: str) -> None:
        self.base_url = base_url.rstrip("/")
        self.cookies = CookieJar()
        # Create unverified SSL context to bypass certificate check
        context = ssl._create_unverified_context()
        self.opener = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(self.cookies),
            urllib.request.HTTPSHandler(context=context)
        )

    def post_form(self, path: str, data: Dict[str, str], referer: str) -> Tuple[int, str]:
        url = f"{self.base_url}{path}"
        body = urllib.parse.urlencode(data).encode("utf-8")
        request = urllib.request.Request(
            url,
            data=body,
            headers={
                "Accept": "application/json, text/javascript, */*; q=0.01",
                "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
                "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
                "Origin": self.base_url,
                "Referer": f"{self.base_url}{referer}",
                "User-Agent": (
                    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/147.0.0.0 Safari/537.36"
                ),
                "X-Requested-With": "XMLHttpRequest",
            },
        )
        with self.opener.open(request, timeout=30) as response:
            return response.status, response.read().decode("utf-8", errors="replace")

    def login(self, username: str, password_hash: str) -> None:
        status, text = self.post_form(
            "/login",
            {
                "USER_NAME": username,
                "password": password_hash,
                "USER_PASSWD": password_hash,
                "userName": "",
                "URL": urllib.parse.urlparse(self.base_url).netloc,
                "skinColor": "blue",
            },
            "/locale?request_locale=zh_CN",
        )
        if status >= 400:
            raise RuntimeError(f"登录失败，HTTP {status}: {text[:200]}")

    def create_meeting(self, args: argparse.Namespace) -> Tuple[str, str]:
        status, text = self.post_form(
            "/cloudmeet/saveOrUpdateCloudMeet.do",
            {
                "title": args.title,
                "startTime": args.start_time,
                "duration": str(args.duration),
                "meetingType": "1",
                "speaker": "",
                "vip": "",
                "agenda": "",
                "enableVhost": "true",
                "hostNumber": args.host_number,
                "hostEmail": args.host_email or DEFAULT_HOST_EMAIL,
                "hostName": "",
                "enableWhiteList": "true",
                "enableSmallMeet": "true",
                "meetingVideoSrc": "liveSrc",
                "meetingBizType": "cm",
                "allowSalesCallout": "enable",
                "whiteList": "4",
                "whiteListValidRange": WHITE_LIST_VALID_RANGES[args.meeting_privacy],
            },
            "/querySafemeeting",
        )
        if status >= 400:
            raise RuntimeError(f"创建会议失败，HTTP {status}: {text[:500]}")
        meet_id = extract_meet_id(text)
        if not meet_id:
            meet_id = self.find_meeting_id(args.title, args.start_time)
        if not meet_id:
            raise RuntimeError(f"创建会议成功但列表中未找到 meetId: {text[:1000]}")
        return meet_id, text

    def find_meeting_id(self, title: str, start_time: str) -> Optional[str]:
        meetings = self.query_meet_list(start_time.split(" ", 1)[0])
        return find_meeting_id_in_list(meetings, title, start_time)

    def find_meeting_by_title(self, title: str, query_date: str) -> Optional[Dict[str, Any]]:
        meetings = self.query_meet_list(query_date)
        title_matches = [
            item for item in flatten_dicts(meetings)
            if str(item.get("title") or item.get("meetTitle") or item.get("name") or "") == title
        ]
        return sorted(title_matches, key=meeting_sort_key)[-1] if title_matches else None

    def query_meet_list(self, query_date: str) -> Any:
        status, text = self.post_form(
            "/cloudmeet/queryMeetListByDay.do",
            {
                "pageNo": "1",
                "pageSize": "100",
                "meetStatus": "",
                "searchKeyWord": "",
                "queryDate": query_date,
            },
            "/querySafemeeting",
        )
        if status >= 400:
            raise RuntimeError(f"获取会议列表失败，HTTP {status}: {text[:500]}")
        return safe_json(text)

    def query_member_list(self, meet_id: str) -> Any:
        status, text = self.post_form(
            "/cloudmeet/getMemberList.do",
            {"pageNo": "1", "pageSize": "10", "meetId": meet_id},
            f"/cloudmeet/meetConfigUI.do?meetId={meet_id}",
        )
        if status >= 400:
            raise RuntimeError(f"获取主持人/嘉宾失败，HTTP {status}: {text[:500]}")
        return safe_json(text)

    def query_white_list(self, meet_id: str) -> Any:
        status, text = self.post_form(
            "/cloudmeet/getWhiteList.do",
            {"pageNo": "1", "pageSize": "10", "meetId": meet_id, "searchKeyWord": ""},
            f"/cloudmeet/meetConfigUI.do?meetId={meet_id}",
        )
        if status >= 400:
            raise RuntimeError(f"获取参会人失败，HTTP {status}: {text[:500]}")
        return safe_json(text)

    def add_member(self, meet_id: str, person: Dict[str, str], role: int) -> str:
        status, text = self.post_form(
            "/cloudmeet/addMemberList.do",
            {
                "name": person.get("name", ""),
                "phone": person.get("phone", ""),
                "email": person.get("email", ""),
                "meetId": meet_id,
                "role": str(role),
                "dept": person.get("dept", ""),
                "company": person.get("company", ""),
                "desc": person.get("desc", ""),
            },
            f"/cloudmeet/meetConfigUI.do?meetId={meet_id}",
        )
        if status >= 400:
            raise RuntimeError(f"添加成员失败，HTTP {status}: {text[:500]}")
        return text

    def add_white_list(self, meet_id: str, person: Dict[str, str]) -> str:
        status, text = self.post_form(
            "/cloudmeet/addWhiteList.do",
            {
                "name": person.get("name", ""),
                "phone": person.get("phone", ""),
                "email": person.get("email", ""),
                "company": person.get("company", ""),
                "dept": person.get("dept", ""),
                "meetId": meet_id,
            },
            f"/cloudmeet/meetConfigUI.do?meetId={meet_id}",
        )
        if status >= 400:
            raise RuntimeError(f"添加参会人失败，HTTP {status}: {text[:500]}")
        return text


def extract_meet_id(text: str) -> Optional[str]:
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        payload = None

    def walk(value: Any) -> Optional[str]:
        if isinstance(value, dict):
            for key in ("meetId", "meet_id", "meetingId", "safeMeetingId", "id"):
                found = value.get(key)
                if isinstance(found, (str, int)) and str(found).isdigit():
                    return str(found)
            for child in value.values():
                found = walk(child)
                if found:
                    return found
        if isinstance(value, list):
            for child in value:
                found = walk(child)
                if found:
                    return found
        return None

    if payload is not None:
        found = walk(payload)
        if found:
            return found

    match = re.search(r"(?:meetId|meetingId|safeMeetingId|id)[\"'=:\s]+(\d{3,})", text)
    return match.group(1) if match else None


def flatten_dicts(value: Any) -> List[Dict[str, Any]]:
    result = []  # type: List[Dict[str, Any]]
    if isinstance(value, dict):
        result.append(value)
        for child in value.values():
            result.extend(flatten_dicts(child))
    elif isinstance(value, list):
        for child in value:
            result.extend(flatten_dicts(child))
    return result


def contains_phone(value: Any, phone: str) -> bool:
    return phone in json.dumps(value, ensure_ascii=False)


def member_has_role(member_list: Any, phone: str, role: int) -> bool:
    for item in flatten_dicts(member_list):
        if str(item.get("phone") or "") != phone:
            continue
        item_role = item.get("role")
        if item_role is not None and int(item_role) == role:
            return True
    return False


def find_meeting_id_in_list(meetings: Any, title: str, start_time: str) -> Optional[str]:
    title_matches = [
        item for item in flatten_dicts(meetings)
        if str(item.get("title") or item.get("meetTitle") or item.get("name") or "") == title
    ]
    exact_matches = [
        item for item in title_matches
        if start_time in json.dumps(item, ensure_ascii=False)
    ]
    candidates = exact_matches or sorted(title_matches, key=meeting_sort_key)
    return extract_meet_id(json.dumps(candidates[-1], ensure_ascii=False)) if candidates else None


def meeting_sort_key(item: Dict[str, Any]) -> str:
    return str(item.get("startdate") or item.get("appointDate") or item.get("createDate") or "")


def load_people(raw: Optional[str]) -> List[Dict[str, str]]:
    if not raw:
        return []
    people = json.loads(raw)
    if not isinstance(people, list):
        raise ValueError("人员参数必须是 JSON 数组")
    for person in people:
        if not isinstance(person, dict) or not person.get("name") or not person.get("phone"):
            raise ValueError("每个人员必须包含 name 和 phone")
    return people


def default_start_time() -> str:
    value = dt.datetime.now() + dt.timedelta(minutes=20)
    value = value.replace(second=0, microsecond=0)
    return value.strftime("%Y-%m-%d %H:%M:%S")


def today() -> str:
    return dt.datetime.now().strftime("%Y-%m-%d")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="263 安全会议正式环境 HTTP 自动创建脚本")
    parser.add_argument("--base-url", default=os.getenv("SAFEMEETING_BASE_URL", DEFAULT_BASE_URL))
    parser.add_argument("--username", default=os.getenv("SAFEMEETING_USERNAME", DEFAULT_USERNAME))
    parser.add_argument("--password-hash", default=os.getenv("SAFEMEETING_PASSWORD_HASH", DEFAULT_PASSWORD_HASH))
    parser.add_argument("--title", default="测试会议")
    parser.add_argument("--start-time", default=default_start_time())
    parser.add_argument("--duration", type=int, default=120)
    parser.add_argument("--host-number", default=os.getenv("SAFEMEETING_HOST_NUMBER", DEFAULT_HOST_NUMBER))
    parser.add_argument("--host-email", default=os.getenv("SAFEMEETING_HOST_EMAIL", ""))
    parser.add_argument("--meeting-privacy", choices=("open", "limited", "public", "private"), default="open", help="创建会议类型：open 公开会议，limited 小范围会议；public/private 为兼容旧命令的别名")
    parser.add_argument("--existing-title", default="", help="指定已有会议名称时，只查询该会议并加人，不创建新会议")
    parser.add_argument("--meeting-date", default=today(), help="查询已有会议的日期，格式 YYYY-MM-DD，默认今天")
    parser.add_argument("--hosts-json", default=None, help="主持人 JSON 数组，role=1；未提供时使用默认主持人，传 [] 可跳过")
    parser.add_argument("--guests-json", default=None, help="嘉宾 JSON 数组，role=2；未提供时使用默认嘉宾，传 [] 可跳过")
    parser.add_argument("--participants-json", default="[]", help="参会人 JSON 数组，添加到会议级白名单")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    if not args.password_hash:
        print("缺少 --password-hash 或 SAFEMEETING_PASSWORD_HASH", file=sys.stderr)
        return 2

    hosts = load_people(args.hosts_json if args.hosts_json is not None else DEFAULT_HOSTS_JSON)
    guests = load_people(args.guests_json if args.guests_json is not None else DEFAULT_GUESTS_JSON)
    participants = load_people(args.participants_json)

    client = SafeMeetingClient(args.base_url)
    client.login(args.username, args.password_hash)
    if args.existing_title:
        meeting = client.find_meeting_by_title(args.existing_title, args.meeting_date)
        if not meeting:
            raise RuntimeError(f"未在 {args.meeting_date} 找到会议：{args.existing_title}")
        meet_id = extract_meet_id(json.dumps(meeting, ensure_ascii=False))
        if not meet_id:
            raise RuntimeError(f"找到会议但未识别 meetId: {json.dumps(meeting, ensure_ascii=False)}")
        title = str(meeting.get("title") or args.existing_title)
        start_time = str(meeting.get("startdate") or meeting.get("appointDate") or "")
        duration = meeting.get("last") or ""
        create_response = None
    else:
        meet_id = client.find_meeting_id(args.title, args.start_time)
        if meet_id:
            create_response = None
            title = args.title
            start_time = args.start_time
            duration = args.duration
            mode = "resumed"
        else:
            meet_id, create_response = client.create_meeting(args)
            title = args.title
            start_time = args.start_time
            duration = args.duration
            mode = "create"

    result: dict[str, Any] = {
        "meetId": meet_id,
        "title": title,
        "startTime": start_time,
        "duration": duration,
        "mode": "existing" if args.existing_title else mode,
        "meetingPrivacy": args.meeting_privacy if not args.existing_title else None,
        "meetingTypeLabel": MEETING_TYPE_LABELS[args.meeting_privacy] if not args.existing_title else None,
        "createSkipped": mode == "resumed",
        "createResponse": safe_json(create_response) if create_response is not None else None,
        "meetingListConfirmed": contains_phone(
            client.query_meet_list((start_time or args.meeting_date).split(" ", 1)[0]),
            meet_id,
        ),
        "added": {"hosts": [], "guests": [], "participants": []},
    }

    member_list = client.query_member_list(meet_id)
    for person in hosts:
        if member_has_role(member_list, person["phone"], 1):
            result["added"]["hosts"].append({
                "person": person,
                "response": None,
                "confirmed": True,
                "skipped": True,
            })
            continue
        response = client.add_member(meet_id, person, 1)
        member_list = client.query_member_list(meet_id)
        result["added"]["hosts"].append({
            "person": person,
            "response": safe_json(response),
            "confirmed": member_has_role(member_list, person["phone"], 1),
            "skipped": False,
        })
    for person in guests:
        if member_has_role(member_list, person["phone"], 2):
            result["added"]["guests"].append({
                "person": person,
                "response": None,
                "confirmed": True,
                "skipped": True,
            })
            continue
        response = client.add_member(meet_id, person, 2)
        member_list = client.query_member_list(meet_id)
        result["added"]["guests"].append({
            "person": person,
            "response": safe_json(response),
            "confirmed": member_has_role(member_list, person["phone"], 2),
            "skipped": False,
        })
    white_list = client.query_white_list(meet_id)
    for person in participants:
        if contains_phone(white_list, person["phone"]):
            result["added"]["participants"].append({
                "person": person,
                "response": None,
                "confirmed": True,
                "skipped": True,
            })
            continue
        response = client.add_white_list(meet_id, person)
        white_list = client.query_white_list(meet_id)
        result["added"]["participants"].append({
            "person": person,
            "response": safe_json(response),
            "confirmed": contains_phone(white_list, person["phone"]),
            "skipped": False,
        })

    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


def safe_json(text: str) -> Any:
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return text


if __name__ == "__main__":
    raise SystemExit(main())
