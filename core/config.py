"""
配置加载 / 保存 / 校验。

字段说明见 config/config.example.json。
"""
from __future__ import annotations

import json
from typing import Any

from core.paths import CONFIG_PATH

# 全部可配置字段及其默认值（新用户拿到的空配置）
DEFAULT_CONFIG: dict[str, Any] = {
    "username": "",
    "password": "",
    "schoolid": "",
    "address": "",
    "location": "",
    "remark": "",
    "pictureAry": [],
    # --- 以下为桌面软件新增字段 ---
    "planId": "",          # 目标实习计划 ID；空则自动选"唯一进行中"的计划
    "amap_key": "",        # 高德 API Key；留空则选址退化为纯手动
    "clockin_type_default": "0",   # 静默模式默认打卡类型：0=上班 1=下班
}

# 必填字段（缺失则打卡无法执行）
REQUIRED_FIELDS = ("username", "password", "address", "location")


def load_config() -> dict[str, Any]:
    """加载配置，缺失字段用默认值补齐。文件不存在则返回全默认。"""
    config = DEFAULT_CONFIG.copy()
    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            user_config = json.load(f)
        if isinstance(user_config, dict):
            config.update(user_config)
    except FileNotFoundError:
        pass
    except json.JSONDecodeError as e:
        # 配置文件损坏时不覆盖，让校验环节报错
        print(f"[config] 配置文件解析失败（{e}），使用默认值。请检查 {CONFIG_PATH}")
    return config


def save_config(config: dict[str, Any]) -> tuple[bool, str]:
    """
    保存配置到 JSON。
    返回 (ok, error_message)。不会抛出异常——调用方不需要 try/except。
    """
    try:
        from core.paths import ensure_dirs
        ok, err = ensure_dirs()
        if not ok:
            return False, err
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(config, f, ensure_ascii=False, indent=2)
        return True, ""
    except OSError as e:
        return False, f"写入配置失败：{e}"


def validate_config(config: dict[str, Any] | None = None) -> list[str]:
    """
    返回缺失的必填字段名列表。空列表表示校验通过。
    """
    if config is None:
        config = load_config()
    missing = [f for f in REQUIRED_FIELDS if not str(config.get(f, "")).strip()]
    return missing
