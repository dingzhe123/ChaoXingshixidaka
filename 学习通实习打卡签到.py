"""
学习通实习打卡签到 — CLI 薄壳

原脚本的核心逻辑已迁移至 core/ 包。本文件保留 CLI 菜单交互，
让老用户和 README 里的用法不失效。

新用户请使用「打卡助手.exe」（GUI）。
"""
import sys
import os
import time
from tkinter import filedialog

import requests

# ==================== 路径解析 ====================
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from core.paths import CONFIG_PATH
from core.config import load_config, validate_config
from core.net import make_session, USER_AGENT
from core.auth import login
from core.clockin import clockin_main, fetch_plans, resolve_target_plan

config = load_config()


def cli_log(msg: str) -> None:
    """CLI 日志：打印到控制台。"""
    print(f"[{time.strftime('%H:%M:%S')}] {msg}")


def cli_clockin():
    """CLI 打卡流程。"""
    missing = validate_config(config)
    if missing:
        print(f"配置缺失：{', '.join(missing)}")
        return

    session = make_session()
    auth = login(config["username"], config["password"], config.get("schoolid", ""))
    if not auth.ok:
        print(f"登录失败：{auth.error_msg}")
        return

    cli_log("登录成功，正在获取实习计划...")
    plans = fetch_plans(session, on_log=cli_log)
    if plans is None:
        print("登录失效")
        return
    if not plans:
        print("未找到实习计划")
        return

    plan = resolve_target_plan(plans, config.get("planId", ""), on_log=cli_log)
    if plan is None:
        print("无法确定目标计划")
        return

    # 列出计划让用户选（仅在未配置 planId 且有多个计划时）
    if not config.get("planId") and len(plans) > 1:
        for i, p in enumerate(plans, 1):
            print(f"  {i}. {p.name} [{p.plan_status}]")
        while True:
            try:
                idx = int(input("选择计划编号: "))
                if 1 <= idx <= len(plans):
                    plan = plans[idx - 1]
                    break
            except ValueError:
                pass
            print("输入错误")

    while True:
        t = input("0=上班打卡, 1=下班打卡: ")
        if t in ("0", "1"):
            break
        print("输入错误")

    result = clockin_main(session, t, config, on_log=cli_log)
    print(f"\n结果: {result.message}")
    if result.detail:
        print(f"详情: {result.detail[:200]}")
    time.sleep(2)


def upload_img():
    """上传打卡图片（保留 tkinter 文件选择）。"""
    import filetype

    resp = login(config["username"], config["password"], config.get("schoolid", ""))
    if not resp.ok:
        print(f"登录失败：{resp.error_msg}")
        time.sleep(2)
        return

    session = resp.session
    while True:
        filepath = filedialog.askopenfilename(title="选择拍照图片",
                                               filetypes=(("图片文件", "*.jpg;*.png;*.gif;*.webp;*.bmp"),))
        if not filepath:
            return
        file_guess = filetype.guess(filepath)
        if file_guess and file_guess.extension in ("jpg", "png", "gif", "webp", "bmp"):
            break
        print("不是图片文件，请重新选择")

    upload_url = "https://sx.chaoxing.com/internship/usts/file"
    with open(filepath, "rb") as f:
        res = session.post(upload_url, headers={"User-Agent": USER_AGENT},
                           files={"file": f}, timeout=(5, 30))
    if res.url == upload_url:
        data = res.json()
        if data.get("result") == 0:
            print(f"上传成功，文件ID: {data['data']['objectid']}")
            print("请将其粘贴到 config.json 的 pictureAry 列表中")
        else:
            print(f"上传失败: {data.get('errorMsg')}")
    else:
        print("登录失效")
    time.sleep(2)


if __name__ == "__main__":
    if not config["username"] or not config["password"]:
        print("❌ 配置缺失：请在 config/config.json 中填写 username 和 password")
        print("   参考 config/config.example.json")
        exit(1)

    while True:
        print("\n欢迎使用学习通实习打卡签到脚本")
        print("0. 开始打卡")
        print("1. 上传打卡图片")
        print("2. 退出")
        useid = input("请输入功能序号：")
        if useid == "0":
            cli_clockin()
        elif useid == "1":
            upload_img()
        else:
            break
