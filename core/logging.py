"""
文件日志 —— 静默模式与 GUI 共用。

写 logs/checkin_YYYY-MM-DD.log，启动时清理 30 天前的文件。
"""
from __future__ import annotations

import os
import time

from core.paths import LOG_DIR


def _today() -> str:
    return time.strftime("%Y-%m-%d")


def _cleanup_old_logs(retain_days: int = 30) -> None:
    """删除超过 retain_days 天的日志文件。静默调用，失败不影响主流程。"""
    if not os.path.isdir(LOG_DIR):
        return
    cutoff = time.time() - retain_days * 86400
    try:
        for name in os.listdir(LOG_DIR):
            if not name.endswith(".log"):
                continue
            path = os.path.join(LOG_DIR, name)
            try:
                if os.path.getmtime(path) < cutoff:
                    os.remove(path)
            except OSError:
                pass
    except OSError:
        pass


def log_message(message: str, level: str = "INFO") -> str:
    """
    写入日志文件并返回写入的文本（供调用方同时显示在界面上）。
    """
    ts = time.strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] [{level}] {message}"

    try:
        os.makedirs(LOG_DIR, exist_ok=True)
        with open(os.path.join(LOG_DIR, f"checkin_{_today()}.log"), "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except OSError:
        pass  # 日志写入失败不应中断打卡流程

    # 顺便清理旧日志（每天第一次写入时检查一次即可，开销可忽略）
    if not hasattr(log_message, "_cleaned_today"):
        log_message._cleaned_today = ""
    if log_message._cleaned_today != _today():
        log_message._cleaned_today = _today()
        _cleanup_old_logs()

    return line
