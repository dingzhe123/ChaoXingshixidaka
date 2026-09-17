"""
登录模块：创建认证 session。

对应原脚本 clockin_main() 中的：
    session.post('https://passport2.chaoxing.com/api/login?...').json()
"""
from __future__ import annotations

import requests

from core.net import make_session, request_with_retry

LOGIN_URL = "https://passport2.chaoxing.com/api/login"


class AuthResult:
    """登录结果。"""
    __slots__ = ("ok", "session", "error_msg")

    def __init__(self, ok: bool, session: requests.Session | None = None, error_msg: str = ""):
        self.ok = ok
        self.session = session
        self.error_msg = error_msg


def login(username: str, password: str, schoolid: str = "") -> AuthResult:
    """
    登录学习通，返回携带认证 cookie 的 session。
    网络异常时返回 error_msg，不抛出。
    """
    session = make_session()
    params = f"name={username}&pwd={password}&schoolid={schoolid}&verify=0"
    url = f"{LOGIN_URL}?{params}"

    try:
        resp = request_with_retry(session.post, url)
        data = resp.json()
    except requests.exceptions.RequestException as e:
        return AuthResult(False, error_msg=f"登录请求失败：{e}")
    except ValueError:
        return AuthResult(False, error_msg="登录响应不是有效 JSON")

    if data.get("result"):
        return AuthResult(True, session=session)
    return AuthResult(False, error_msg=data.get("errorMsg", "登录失败，请检查账号密码"))
