"""
网络层：统一 session 工厂 + 超时 + 重试。

所有 HTTP 请求必须经过本模块，禁止在业务代码里直接 requests.get/post。
原因：打包后的静默 exe 如果卡住不退出，计划任务会不断堆积。
"""
from __future__ import annotations

import time
from typing import Callable

import requests

# 与原脚本保持一致的 UA（学习通接口校验 UA）
USER_AGENT = (
    "Mozilla/5.0 (Linux; Android 12; Redmi K30 Pro Zoom Edition Build/SKQ1.211006.001; wv) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/95.0.4638.74 Mobile Safari/537.36 "
    "(device:Redmi K30 Pro Zoom Edition) Language/zh_CN com.chaoxing.mobile/ChaoXingStudy_3_6.2.8_android_phone_1050_234 "
    "(@Kalimdor)_8c0587fc07ee4c25bdbbb5d7a90d8152"
)

# 超时设置（连接 5s / 读取 15s）
TIMEOUT = (5, 15)


def make_session() -> requests.Session:
    """创建配置好 headers 与默认超时的 session。"""
    s = requests.Session()
    s.headers["User-Agent"] = USER_AGENT
    return s


def request_with_retry(
    fn: Callable[..., requests.Response],
    *args,
    retries: int = 3,
    backoff: float = 30.0,
    **kwargs,
) -> requests.Response:
    """
    带重试的请求封装。超时异常重试最多 retries 次，间隔 backoff 秒。
    所有调用统一注入 timeout=TIMEOUT（调用方不必再传）。
    """
    kwargs.setdefault("timeout", TIMEOUT)
    last_err: Exception | None = None
    for attempt in range(1, retries + 1):
        try:
            return fn(*args, **kwargs)
        except requests.exceptions.Timeout as e:
            last_err = e
            if attempt < retries:
                time.sleep(backoff)
        except requests.exceptions.ConnectionError as e:
            last_err = e
            if attempt < retries:
                time.sleep(backoff)
    # 重试耗尽，抛出最后一个异常
    raise last_err  # type: ignore[misc]
