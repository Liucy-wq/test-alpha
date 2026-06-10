#!/usr/bin/env python3
"""Cancel a 263 safe meeting through captured HTTP APIs."""

import argparse
import json
import os
import ssl
import sys
import urllib.parse
import urllib.request
from http.cookiejar import CookieJar
from typing import Any, Dict, List, Optional, Tuple

DEFAULT_BASE_URL = "https://sec.263.net"
DEFAULT_USERNAME = "lvchen01@rabyte.cn"
DEFAULT_PASSWORD_HASH = "8EC74602A69590199839C5D63A2BD7E9FA3AF6C957EE616D"

class SafeMeetingClient:
    def __init__(self, base_url: str) -> None:
        self.base_url = base_url.rstrip("/")
        self.cookies = CookieJar()
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

    def cancel_meeting(self, meet_id: str) -> str:
        # Try different parameter names and paths
        attempts = [
            ("/cloudmeet/deleteCloudMeet.do", {"ids": meet_id}),
            ("/cloudmeet/deleteCloudMeet.do", {"meetId": meet_id}),
            ("/cloudmeet/cancelCloudMeet.do", {"ids": meet_id}),
            ("/cloudmeet/cancelCloudMeet.do", {"meetId": meet_id}),
            ("/cloudmeet/delCloudMeet.do", {"ids": meet_id}),
            ("/cloudmeet/delCloudMeet.do", {"meetId": meet_id}),
        ]
        last_error = ""
        for path, data in attempts:
            try:
                status, text = self.post_form(
                    path,
                    data,
                    "/cloudmeet/queryMeetListByDay.do",
                )
                if status < 400:
                    return text
                last_error = f"Path {path} returned HTTP {status}"
            except Exception as e:
                # If it's a 404, we just continue to the next attempt
                last_error = f"Path {path} raised {str(e)}"
        
        raise RuntimeError(f"取消会议失败。系统返回 404 可能意味着接口路径不正确，或该 ID 不存在。最后尝试结果: {last_error}")

def main() -> int:
    parser = argparse.ArgumentParser(description="263 安全会议正式环境取消会议脚本")
    parser.add_argument("meet_ids", nargs="+", help="需要取消的会议 ID 列表")
    parser.add_argument("--base-url", default=os.getenv("SAFEMEETING_BASE_URL", DEFAULT_BASE_URL))
    parser.add_argument("--username", default=os.getenv("SAFEMEETING_USERNAME", DEFAULT_USERNAME))
    parser.add_argument("--password-hash", default=os.getenv("SAFEMEETING_PASSWORD_HASH", DEFAULT_PASSWORD_HASH))
    
    args = parser.parse_args()
    
    client = SafeMeetingClient(args.base_url)
    client.login(args.username, args.password_hash)
    
    results = []
    for meet_id in args.meet_ids:
        try:
            response_text = client.cancel_meeting(meet_id)
            try:
                response = json.loads(response_text)
            except:
                response = response_text
            results.append({
                "meetId": meet_id,
                "success": True,
                "response": response
            })
        except Exception as e:
            results.append({
                "meetId": meet_id,
                "success": False,
                "error": str(e)
            })
            
    print(json.dumps(results, ensure_ascii=False, indent=2))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
