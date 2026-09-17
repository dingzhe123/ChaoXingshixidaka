"""
静默入口 — 由 后台打卡.exe 构建目标引用。

【关键约束】本文件不得 import 任何 GUI 模块（PyQt5、tkinter）。
任何 GUI 的 import 都必须藏在函数里也不行——PyInstaller 静态分析
会无条件打包所有被引用的模块。

流程: 加载配置 → 校验 → 建 session → 登录 → 幂等检查 → 随机抖动 → 打卡 → 退出

退出码:
    0 = 成功，或今日已打卡（无需再打）
    1 = 打卡失败（已弹窗通知）
    2 = 配置缺失 / 目录不可写
    3 = 登录失败 / 无法确定目标计划
"""
import argparse
import random
import sys
import os

# 把项目根加入 sys.path，确保 core/ 可被导入
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.paths import BASE_DIR, check_writable, ensure_dirs
from core.config import load_config, validate_config
from core.net import make_session
from core.auth import login
from core.clockin import clockin_main, today_clockin_status
from core.logging import log_message

LAST_ERROR_PATH = os.path.join(BASE_DIR, "logs", "last_error.txt")


def _notify_failure(msg: str) -> None:
    """
    失败通知。
    成功时完全静默（不弹任何窗口），失败时用 Windows 消息框主动告知。
    零依赖实现：ctypes 调 MessageBoxW。
    """
    try:
        import ctypes
        ctypes.windll.user32.MessageBoxW(0, msg, "学习通打卡失败", 0x30)
    except Exception:
        pass  # 通知失败不应影响退出码


def _write_last_error(msg: str) -> None:
    """写 last_error.txt，供 GUI 下次启动时提示。"""
    try:
        os.makedirs(os.path.dirname(LAST_ERROR_PATH), exist_ok=True)
        with open(LAST_ERROR_PATH, "w", encoding="utf-8") as f:
            f.write(msg)
    except OSError:
        pass


def main():
    parser = argparse.ArgumentParser(description="学习通实习打卡 — 静默模式")
    parser.add_argument("--type", choices=["0", "1"], default="0",
                        help="0=上班打卡, 1=下班打卡")
    args = parser.parse_args()

    # 1. 目录检测（D2）
    ok, err = ensure_dirs()
    if not ok:
        print(f"[silent] 目录创建失败: {err}", file=sys.stderr)
        return 2

    ok, err = check_writable()
    if not ok:
        print(f"[silent] {err}", file=sys.stderr)
        return 2

    # 2. 加载 + 校验配置
    config = load_config()
    missing = validate_config(config)
    if missing:
        msg = f"配置缺失：{', '.join(missing)}，请在「打卡助手.exe」中填写"
        log_message(msg, "ERROR")
        _write_last_error(msg)
        _notify_failure(msg)
        return 2

    clockin_type = args.type

    # 3. 登录
    log_message(f"静默模式启动，type={'上班' if clockin_type == '0' else '下班'}")
    session = make_session()
    auth = login(config["username"], config["password"], config.get("schoolid", ""))
    if not auth.ok:
        msg = f"登录失败：{auth.error_msg}"
        log_message(msg, "ERROR")
        _write_last_error(msg)
        _notify_failure(msg)
        return 3

    log_message("登录成功")

    # 4. 幂等检查（D4）—— 先拉计划列表才能查今日状态
    from core.clockin import fetch_plans, resolve_target_plan
    plans = fetch_plans(session, on_log=log_message)
    if plans is None:
        msg = "登录失效（获取计划时被重定向）"
        log_message(msg, "ERROR")
        _write_last_error(msg)
        _notify_failure(msg)
        return 3

    plan = resolve_target_plan(plans, config.get("planId", ""), on_log=log_message)
    if plan is None:
        msg = "无法确定目标计划，请在配置中指定 planId"
        log_message(msg, "ERROR")
        _write_last_error(msg)
        _notify_failure(msg)
        return 3

    # 5. 今日是否已打卡
    existing = today_clockin_status(session, plan.plan_id, on_log=log_message)
    if existing is not None:
        # TODO: 待抓真实响应后完善 type=0/1 区分。当前保守处理：不跳过。
        log_message(f"今日已有打卡记录，仍继续提交（幂等逻辑待完善）")

    # 6. 随机抖动（D5）—— 避免整点整秒的机器特征
    jitter = random.randint(0, 180)
    if jitter > 0:
        log_message(f"随机延迟 {jitter} 秒")
        import time
        time.sleep(jitter)

    # 7. 执行打卡
    result = clockin_main(session, clockin_type, config, on_log=log_message)

    if result.success:
        log_message(f"打卡成功（{result.api_version}）: {result.message}")
        return 0
    else:
        msg = f"打卡失败：{result.message}"
        log_message(msg, "ERROR")
        _write_last_error(msg)
        _notify_failure(msg)
        return 1


if __name__ == "__main__":
    sys.exit(main())
