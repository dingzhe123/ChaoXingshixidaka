"""
打卡核心逻辑。

从 学习通实习打卡签到.py 重构而来：
  · 去掉所有 input() / print()，改为参数 + 日志回调
  · 修复原脚本中的 bug（未定义变量、type 硬编码、正则裸抛）
  · 所有网络请求带 timeout（经 core/net.py）
  · 返回结构化的 ClockinResult

三段回退链：新版 → 旧版1 → 旧版2
"""
from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass, field
from typing import Callable, Optional

import requests

from core.net import request_with_retry

# 原脚本中"被重定向 = 登录失效"的检测基线
def _is_redirected(resp: requests.Response, expected_url: str) -> bool:
    return resp.url != expected_url


# --------------------------------------------------------------------------- #
# 结构化结果
# --------------------------------------------------------------------------- #
@dataclass
class ClockinResult:
    """单次打卡尝试的结果。"""
    success: bool
    message: str
    detail: str = ""        # 原始响应文本，供日志排查
    api_version: str = ""   # "new" / "old1" / "old2"，标识走的是哪段链路


@dataclass
class ClockinPlan:
    """实习计划摘要。"""
    plan_id: str
    plan_user_id: str
    fid: str
    name: str
    plan_status: str        # 进行中 / 已结束 / 未开始
    sx_status: str
    start_time: str
    end_time: str
    recruit_names: str


# --------------------------------------------------------------------------- #
# 日志回调类型
# --------------------------------------------------------------------------- #
LogFn = Optional[Callable[[str], None]]


def _log(fn: LogFn, msg: str) -> None:
    if fn:
        fn(msg)


# --------------------------------------------------------------------------- #
# 计划列表拉取
# --------------------------------------------------------------------------- #
def fetch_plans(session: requests.Session, on_log: LogFn = None) -> list[ClockinPlan] | None:
    """
    拉取实习计划列表。
    返回 None 表示登录失效，返回 [] 表示无计划。
    """
    url = "https://sx.chaoxing.com/internship/planUser/myPlanList"
    try:
        resp = request_with_retry(session.get, url)
    except requests.exceptions.RequestException as e:
        _log(on_log, f"[新版] 请求失败：{e}")
        return None

    if _is_redirected(resp, url):
        _log(on_log, "[新版] 被重定向，登录已失效")
        return None

    data = resp.json()
    if data.get("result") != 0 or not data.get("data"):
        _log(on_log, f"[新版] 无实习计划（{data.get('errorMsg', '未知')}）")
        return []

    plans = []
    for d in data["data"]:
        status_map = {1: "进行中", 2: "已结束", 3: "未开始"}
        sx_map = {0: "未实习", 1: "实习中", 2: "免实习", 3: "终止实习"}
        plans.append(ClockinPlan(
            plan_id=str(d.get("planId", "")),
            plan_user_id=str(d.get("id", "")),
            fid=str(d.get("fid", "")),
            name=d.get("planName", ""),
            plan_status=status_map.get(d.get("planStatus"), "?"),
            sx_status=sx_map.get(d.get("sxStatus"), "?"),
            start_time=d.get("planStartTime", ""),
            end_time=d.get("planEndTime", ""),
            recruit_names=d.get("recruitNames", ""),
        ))
    return plans


# --------------------------------------------------------------------------- #
# 目标计划解析（D8：不能"猜"）
# --------------------------------------------------------------------------- #
def resolve_target_plan(
    plans: list[ClockinPlan],
    configured_plan_id: str,
    on_log: LogFn = None,
) -> ClockinPlan | None:
    """
    从计划列表中确定要打哪一个。
      · 配置了 planId → 精确匹配
      · 未配置 → 仅当"进行中"的计划唯一时才自动选，否则返回 None
    """
    if not plans:
        return None

    if configured_plan_id:
        for p in plans:
            if p.plan_id == configured_plan_id:
                _log(on_log, f"[计划] 使用配置指定的计划：{p.name}")
                return p
        _log(on_log, f"[计划] 配置的 planId={configured_plan_id} 不在列表中")
        return None

    active = [p for p in plans if p.plan_status == "进行中"]
    if len(active) == 1:
        _log(on_log, f"[计划] 自动选择唯一进行中的计划：{active[0].name}")
        return active[0]

    if len(active) == 0:
        _log(on_log, "[计划] 没有进行中的实习计划")
    else:
        _log(on_log, f"[计划] 有 {len(active)} 个进行中的计划，无法自动选择，请在配置中指定 planId")
    return None


# --------------------------------------------------------------------------- #
# 幂等检查（D4）：今日是否已打卡
# --------------------------------------------------------------------------- #
def today_clockin_status(
    session: requests.Session,
    plan_id: str,
    on_log: LogFn = None,
) -> dict | None:
    """
    查询今日打卡记录。
    返回响应中的 data 字段（dict），或 None（查询失败 / 无记录）。
    具体字段结构需在实现后抓真实响应确认。
    """
    today = time.strftime("%Y-%m-%d")
    url = f"https://sx.chaoxing.com/internship/clockin-user/get/stu/{plan_id}/date?date={today}"
    try:
        resp = request_with_retry(session.get, url)
    except requests.exceptions.RequestException as e:
        _log(on_log, f"[幂等] 请求失败：{e}")
        return None

    if _is_redirected(resp, url):
        _log(on_log, "[幂等] 被重定向，登录已失效")
        return None

    data = resp.json()
    if data.get("result") != 0:
        _log(on_log, f"[幂等] 接口返回错误：{data.get('errorMsg', '未知')}")
        return None

    return data.get("data")  # 可能为 None（今日无记录）


# --------------------------------------------------------------------------- #
# 新版打卡（原 new_clockin 重构）
# --------------------------------------------------------------------------- #
def _new_clockin(
    session: requests.Session,
    plan: ClockinPlan,
    clockin_type: str,          # "0"=上班, "1"=下班
    config: dict,
    on_log: LogFn = None,
) -> ClockinResult:
    """新版打卡链路。clockin_type 由调用方指定，不再 input()。"""

    _log(on_log, f"[新版] 获取计划详情 planId={plan.plan_id}")

    detail_url = (
        "https://sx.chaoxing.com/internship/planUser/getDataById"
        f"?planId={plan.plan_id}&planUserId={plan.plan_user_id}"
    )
    try:
        resp = request_with_retry(session.get, detail_url)
    except requests.exceptions.RequestException as e:
        return ClockinResult(False, f"[新版] 请求失败：{e}", api_version="new")

    if _is_redirected(resp, detail_url):
        return ClockinResult(False, "[新版] 登录失效", api_version="new")

    res = resp.json()
    if res.get("result") != 0 or res.get("data") is None:
        return ClockinResult(False, f"[新版] {res.get('errorMsg', '未知错误')}", api_version="new")

    periods = res["data"].get("userPeriods") or []
    if periods:
        recruit_vo = periods[0].get("planUserRecruit", {}).get("recruitVo", {})
        work_start = recruit_vo.get("workStart", "")
        work_end = recruit_vo.get("workEnd", "")
    else:
        work_start = work_end = ""

    cfg_url = f"https://sx.chaoxing.com/internship/dgsxpc/{plan.plan_id}"
    try:
        resp = request_with_retry(session.get, cfg_url)
    except requests.exceptions.RequestException as e:
        return ClockinResult(False, f"[新版] 获取配置失败：{e}", api_version="new")

    if _is_redirected(resp, cfg_url):
        return ClockinResult(False, "[新版] 登录失效", api_version="new")

    res = resp.json()
    if res.get("result") != 0 or res.get("data") is None:
        return ClockinResult(False, f"[新版] {res.get('errorMsg', '未知错误')}", api_version="new")

    is_ontimesign = res["data"].get("isontimesign")
    allow_offset = res["data"].get("offset") or 2000

    date_url = (
        f"https://sx.chaoxing.com/internship/clockin-user/get/stu/{plan.plan_id}/date"
        f"?date={time.strftime('%Y-%m-%d')}"
    )
    try:
        resp = request_with_retry(session.get, date_url)
    except requests.exceptions.RequestException as e:
        return ClockinResult(False, f"[新版] 获取今日记录失败：{e}", api_version="new")

    if _is_redirected(resp, date_url):
        return ClockinResult(False, "[新版] 登录失效", api_version="new")

    res = resp.json()
    if res.get("result") != 0 or res.get("data") is None:
        return ClockinResult(False, f"[新版] {res.get('errorMsg', '未知错误')}", api_version="new")

    rec = res["data"]
    cxid = rec.get("cxid", "")
    clockin_id = rec.get("id", "")
    recruit_id = rec.get("recruitId", "")
    pcid = rec.get("pcid", "")
    pcmajorid = rec.get("pcmajorid", "")

    if is_ontimesign:
        add_url = f"https://sx.chaoxing.com/internship/clockin-user/stu/addclockin/{cxid}"
    else:
        add_url = f"https://sx.chaoxing.com/internship/clockin-user/stu/addclockinOnceInDay/{cxid}"

    status_name = "上班" if clockin_type == "0" else "下班"

    payload = {
        "id": clockin_id,
        "type": clockin_type,
        "recruitId": recruit_id,
        "pcid": pcid,
        "pcmajorid": pcmajorid,
        "address": config.get("address", ""),
        "geolocation": config.get("location", ""),
        "remark": config.get("remark", ""),
        "workStart": work_start,
        "workEnd": work_end,
        "images": json.dumps(config.get("pictureAry", [])) if config.get("pictureAry") else "",
        "allowOffset": allow_offset,
        "offset": "NaN",
        "offduty": 0,
        "codecolor": "",
        "havestar": "",
        "worktype": "",
        "changeLocation": "",
        "statusName": status_name,
        "shouldSignAddress": "",
    }

    _log(on_log, f"[新版] 提交{status_name}打卡")
    try:
        resp = request_with_retry(session.post, add_url, data=payload)
    except requests.exceptions.RequestException as e:
        return ClockinResult(False, f"[新版] 提交失败：{e}", api_version="new")

    if _is_redirected(resp, add_url):
        return ClockinResult(False, "[新版] 登录失效", api_version="new")

    return ClockinResult(True, f"[新版]{status_name}打卡成功", detail=resp.text, api_version="new")


# --------------------------------------------------------------------------- #
# 旧版打卡 1（原 old_clockin1 重构）
# --------------------------------------------------------------------------- #
def _old_clockin1(
    session: requests.Session,
    clockin_type: str,
    config: dict,
    on_log: LogFn = None,
) -> ClockinResult:
    """旧版页面 1 打卡。"""

    _log(on_log, "[旧版1] 获取页面...")
    try:
        resp = request_with_retry(
            session.get,
            "https://www.dgsx.chaoxing.com/form/mobile/signIndex",
        )
    except requests.exceptions.RequestException as e:
        return ClockinResult(False, f"[旧版1] 请求失败：{e}", api_version="old1")

    txt = resp.text
    if txt == "您还没有被分配实习计划。":
        return ClockinResult(False, "[旧版1] 未找到实习打卡任务", api_version="old1")
    if "用户登录状态异常，请重新登录！" in txt:
        return ClockinResult(False, "[旧版1] 登录失效", api_version="old1")

    # 正则健壮性修复：原脚本 .groups() 无匹配时直接抛 AttributeError
    try:
        plan_name = re.search(r"planName: '(.*)'", txt, re.I).group(1)
        page_type = re.search(r"type: '(.*)'", txt, re.I).group(1)
        sign_type = re.search(r"signType: '(.*)'", txt, re.I).group(1)
        work_address = re.search(
            r'<input type="hidden" id="workAddress" value="(.*)"/>', txt, re.I
        ).group(1)
        work_location = re.search(
            r'<input type="hidden" id="workLocation" value="(.*)">', txt, re.I
        ).group(1)
        allow_offset = re.search(
            r'<input type="hidden" id="allowOffset" value="(.*)"/>', txt, re.I
        ).group(1)
        sign_setting_id = re.search(
            r'<input type="hidden" id="signSettingId" value="(.*)"/>', txt, re.I
        ).group(1)
    except AttributeError:
        return ClockinResult(False, "[旧版1] 页面结构变化，无法解析", api_version="old1")

    # 修复：原脚本 type 从页面正则抓取，不受用户控制 → 改用参数
    # 修复：原脚本使用了未定义的 remark 变量
    payload = {
        "planName": plan_name,
        "type": clockin_type,
        "signType": sign_type,
        "address": work_address,
        "geolocation": work_location,
        "remark": config.get("remark", ""),
        "images": "",
        "offset": 0,
        "allowOffset": allow_offset,
        "signSettingId": sign_setting_id,
    }

    _log(on_log, "[旧版1] 提交打卡")
    try:
        resp = request_with_retry(
            session.post,
            "https://www.dgsx.chaoxing.com/form/mobile/saveSign",
            data=payload,
        )
    except requests.exceptions.RequestException as e:
        return ClockinResult(False, f"[旧版1] 提交失败：{e}", api_version="old1")

    return ClockinResult(True, "[旧版1] 打卡成功", detail=resp.text, api_version="old1")


# --------------------------------------------------------------------------- #
# 旧版打卡 2（原 old_clockin2 重构）
# --------------------------------------------------------------------------- #
def _old_clockin2(
    session: requests.Session,
    clockin_type: str,
    config: dict,
    on_log: LogFn = None,
) -> ClockinResult:
    """旧版页面 2 打卡。遍历学校站点查找可打卡的计划。"""

    _log(on_log, "[旧版2] 获取用户站点...")
    try:
        resp = request_with_retry(
            session.get,
            "https://i.chaoxing.com/base/cacheUserOrg",
        )
        sites = resp.json().get("site", [])
    except (requests.exceptions.RequestException, ValueError) as e:
        return ClockinResult(False, f"[旧版2] 获取站点失败：{e}", api_version="old2")

    for site in sites:
        fid = str(site.get("fid", ""))
        session.cookies.set("wfwfid", fid)

        try:
            resp = request_with_retry(
                session.get,
                "https://www.dgsx.chaoxing.com/mobile/clockin/show",
            )
        except requests.exceptions.RequestException:
            continue

        txt = resp.text
        if resp.status_code != 200:
            continue
        if "alert('请先登录');" in txt:
            continue
        if 'alert("实习计划已进入总结期或实习已终止，无法签到");' in txt:
            continue
        if "用户登录状态异常，请重新登录！" in txt:
            continue

        try:
            clockin_id = re.search(
                r'<input id="clockinId" type="hidden" value="(.*)">', txt, re.I
            ).group(1)
            recruit_id = re.search(
                r'<input type="hidden" id="recruitId" value="(.*)" />', txt, re.I
            ).group(1)
            pcid = re.search(
                r'<input type="hidden" id="pcid" value="(.*)" />', txt, re.I
            ).group(1)
            pcmajorid = re.search(
                r'<input type="hidden" id="pcmajorid" value="(.*)" />', txt, re.I
            ).group(1)
            should = re.search(
                r'''<dd class="should_bntover" selid="(.*)" workStart='(.*)' workEnd='(.*)'>''',
                txt, re.I,
            ).groups()
            work_start, work_end = should[1], should[2]
            allow_offset = re.search(
                r'<input type="hidden" id="allowOffset" value="(.*)"/>', txt, re.I
            ).group(1)
            change_location = re.search(
                r'<input type="text" name="location" id="location" value="(.*)" hidden/>', txt, re.I
            ).group(1)

            # offset 逻辑照搬原脚本
            if re.search(r'<input id="workLocation" type="hidden" >', txt, re.I) is not None:
                offset = "NaN"
            elif re.search(r'<input id="workLocation" type="hidden" value="(.*)">', txt, re.I) is None:
                offset = "NaN"
            else:
                offset = re.search(
                    r'<input id="workLocation" type="hidden" value="(.*)">', txt, re.I
                ).group(1)
        except AttributeError:
            continue

        # 修复：原脚本 type 硬编码为 0，下班打卡走旧版链路会静默失效
        payload = {
            "id": clockin_id,
            "type": int(clockin_type),      # 旧版接口要整数
            "recruitId": recruit_id,
            "pcid": pcid,
            "pcmajorid": pcmajorid,
            "address": config.get("address", ""),
            "geolocation": config.get("location", ""),
            "remark": config.get("remark", ""),
            "workStart": work_start,
            "workEnd": work_end,
            "images": "",
            "allowOffset": allow_offset,
            "offset": offset,
            "offduty": 0,
            "changeLocation": change_location,
        }

        _log(on_log, f"[旧版2] 提交打卡（站点 fid={fid}）")
        try:
            resp = request_with_retry(
                session.post,
                "https://www.dgsx.chaoxing.com/mobile/clockin/addclockin2",
                data=payload,
            )
        except requests.exceptions.RequestException as e:
            return ClockinResult(False, f"[旧版2] 提交失败：{e}", api_version="old2")

        return ClockinResult(True, "[旧版2] 打卡成功", detail=resp.text, api_version="old2")

    return ClockinResult(False, "[旧版2] 未找到可用的实习打卡任务", api_version="old2")


# --------------------------------------------------------------------------- #
# 编排入口
# --------------------------------------------------------------------------- #
def clockin_main(
    session: requests.Session,
    clockin_type: str,          # "0"=上班, "1"=下班
    config: dict,
    on_log: LogFn = None,
) -> ClockinResult:
    """
    打卡主流程：拉计划 → 解析目标 → 幂等检查 → 新版 → 旧版1 → 旧版2。
    """

    # 1. 拉取计划列表
    plans = fetch_plans(session, on_log)
    if plans is None:
        return ClockinResult(False, "登录失效，请重新登录")
    if not plans:
        return ClockinResult(False, "未找到实习打卡任务")

    # 2. 确定要打哪一个（D8）
    plan = resolve_target_plan(plans, config.get("planId", ""), on_log)
    if plan is None:
        return ClockinResult(False, "无法确定目标计划，请在配置中指定 planId")

    # 3. 幂等检查（D4）
    existing = today_clockin_status(session, plan.plan_id, on_log)
    if existing is not None:
        # TODO: 待抓真实响应后完善——区分 type=0/1 的判断逻辑
        _log(on_log, f"[幂等] 今日已有打卡记录：{existing}")
        # 保守起见暂不跳过，等字段结构确认后再启用跳过逻辑

    # 4. 三段回退链
    result = _new_clockin(session, plan, clockin_type, config, on_log)
    if result.success or "登录失效" in result.message:
        return result

    _log(on_log, f"[回退] 新版未命中（{result.message}），尝试旧版页面1")
    result = _old_clockin1(session, clockin_type, config, on_log)
    if result.success:
        return result

    _log(on_log, f"[回退] 旧版1未命中（{result.message}），尝试旧版页面2")
    return _old_clockin2(session, clockin_type, config, on_log)
