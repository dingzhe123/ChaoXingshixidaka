"""
连接性诊断 —— 只调用读接口，不执行任何打卡操作。

从 test_connection.py 重构而来：
  · 修复登录 URL 中 pwd/password 重复参数的 bug
  · 返回结构化 CheckResult，供 GUI「测试连接」按钮和静默模式复用
  · 所有请求带 timeout（经 core/net.py）
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field

import requests

from core.net import make_session, request_with_retry


@dataclass
class CheckResult:
    """单项诊断结果。"""
    name: str
    ok: bool
    message: str = ""
    data: dict = field(default_factory=dict)


@dataclass
class DiagnosticsReport:
    """全套诊断结果。"""
    login: CheckResult | None = None
    plans: CheckResult | None = None
    clockin_config: CheckResult | None = None
    today_record: CheckResult | None = None
    user_org: CheckResult | None = None

    @property
    def all_ok(self) -> bool:
        return all(getattr(self, f.name).ok for f in self.__dataclass_fields__.values()
                   if getattr(self, f.name) is not None)


# 与原脚本一致的登录 URL；修复了原 test_connection.py:29 的 pwd/password 重复 bug
LOGIN_URL = "https://passport2.chaoxing.com/api/login"


def check_login(session: requests.Session, username: str, password: str, schoolid: str = "") -> CheckResult:
    """测试 1：登录。"""
    params = f"name={username}&pwd={password}&schoolid={schoolid}&verify=0"
    url = f"{LOGIN_URL}?{params}"
    try:
        resp = request_with_retry(session.post, url)
        data = resp.json()
    except requests.exceptions.RequestException as e:
        return CheckResult("login", False, f"请求失败：{e}")
    except ValueError:
        return CheckResult("login", False, "响应不是有效 JSON")

    if data.get("result"):
        return CheckResult("login", True, "登录成功")
    return CheckResult("login", False, data.get("errorMsg", "登录失败"))


def check_my_plan_list(session: requests.Session) -> CheckResult:
    """测试 2：获取实习计划列表。"""
    url = "https://sx.chaoxing.com/internship/planUser/myPlanList"
    try:
        resp = request_with_retry(session.get, url)
    except requests.exceptions.RequestException as e:
        return CheckResult("plans", False, f"请求失败：{e}")

    if resp.url != url:
        return CheckResult("plans", False, "被重定向，登录已失效")

    data = resp.json()
    if data.get("result") == 0 and data.get("data"):
        return CheckResult("plans", True, f"找到 {len(data['data'])} 个实习计划",
                           data={"count": len(data["data"])})
    if data.get("result") == 0:
        return CheckResult("plans", False, "接口正常，但当前没有实习计划")
    return CheckResult("plans", False, data.get("errorMsg", "未知错误"))


def _get_first_plan_id(session: requests.Session) -> str | None:
    """辅助：获取第一个计划的 planId，用于后续测试。"""
    url = "https://sx.chaoxing.com/internship/planUser/myPlanList"
    try:
        resp = request_with_retry(session.get, url)
        if resp.url != url:
            return None
        data = resp.json()
        if data.get("result") == 0 and data.get("data"):
            return str(data["data"][0].get("planId", ""))
    except Exception:
        pass
    return None


def check_clockin_config(session: requests.Session) -> CheckResult:
    """测试 3：获取打卡配置。"""
    plan_id = _get_first_plan_id(session)
    if not plan_id:
        return CheckResult("clockin_config", False, "跳过（无实习计划）")

    url = f"https://sx.chaoxing.com/internship/dgsxpc/{plan_id}"
    try:
        resp = request_with_retry(session.get, url)
    except requests.exceptions.RequestException as e:
        return CheckResult("clockin_config", False, f"请求失败：{e}")

    if resp.url != url:
        return CheckResult("clockin_config", False, "被重定向")

    data = resp.json()
    if data.get("result") == 0 and data.get("data"):
        cfg = data["data"]
        return CheckResult("clockin_config", True,
                           f"实时签到={'是' if cfg.get('isontimesign') else '否'}，偏移量={cfg.get('offset', 'N/A')}米",
                           data={"isontimesign": cfg.get("isontimesign"), "offset": cfg.get("offset")})
    return CheckResult("clockin_config", False, data.get("errorMsg", "未知错误"))


def check_today_record(session: requests.Session) -> CheckResult:
    """测试 4：获取今日打卡记录。"""
    plan_id = _get_first_plan_id(session)
    if not plan_id:
        return CheckResult("today_record", False, "跳过（无实习计划）")

    today = time.strftime("%Y-%m-%d")
    url = f"https://sx.chaoxing.com/internship/clockin-user/get/stu/{plan_id}/date?date={today}"
    try:
        resp = request_with_retry(session.get, url)
    except requests.exceptions.RequestException as e:
        return CheckResult("today_record", False, f"请求失败：{e}")

    if resp.url != url:
        return CheckResult("today_record", False, "被重定向")

    data = resp.json()
    if data.get("result") == 0 and data.get("data"):
        rec = data["data"]
        return CheckResult("today_record", True,
                           f"clockinId={rec.get('id', 'N/A')}, recruitId={rec.get('recruitId', 'N/A')}",
                           data=dict(rec))
    if data.get("result") == 0:
        return CheckResult("today_record", False, "接口正常，今日无打卡记录")
    return CheckResult("today_record", False, data.get("errorMsg", "未知错误"))


def check_user_org(session: requests.Session) -> CheckResult:
    """测试 5：获取用户学校站点（旧版打卡用）。"""
    url = "https://i.chaoxing.com/base/cacheUserOrg"
    try:
        resp = request_with_retry(session.get, url)
        sites = resp.json().get("site", [])
    except requests.exceptions.RequestException as e:
        return CheckResult("user_org", False, f"请求失败：{e}")
    except ValueError:
        return CheckResult("user_org", False, "响应不是有效 JSON")

    return CheckResult("user_org", True, f"找到 {len(sites)} 个站点",
                       data={"count": len(sites)})


def run_diagnostics(username: str, password: str, schoolid: str = "") -> DiagnosticsReport:
    """
    运行全套诊断。返回 DiagnosticsReport。
    登录失败时后续测试自动跳过。
    """
    session = make_session()
    report = DiagnosticsReport()

    report.login = check_login(session, username, password, schoolid)
    if not report.login.ok:
        return report

    report.plans = check_my_plan_list(session)
    report.clockin_config = check_clockin_config(session)
    report.today_record = check_today_record(session)
    report.user_org = check_user_org(session)
    return report
