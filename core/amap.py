"""
高德 Web Service API 薄封装。

仅依赖 requests，无需额外 SDK。所有函数都需要 amap_key；
空 key 直接返回空结果（不抛异常）——调用方应提前检查 key 是否配置。

坐标系：高德返回 GCJ-02（火星坐标），与本软件默认处理方式一致，
调用方无需做转换。详见计划文档 Phase 5。

POI 搜索 API: https://lbs.amap.com/api/webservice/guide/api/newpoisearch
逆地理编码:    https://lbs.amap.com/api/webservice/guide/api/georegeo
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from core.net import request_with_retry

POI_SEARCH_URL = "https://restapi.amap.com/v3/place/text"
REGEOCODE_URL = "https://restapi.amap.com/v3/geocode/regeo"


@dataclass
class PlaceCandidate:
    """单个地址候选项。"""
    name: str
    address: str
    lng: float
    lat: float

    def to_display(self) -> str:
        return f"{self.name} — {self.address}"


def _has_key(amap_key: str) -> bool:
    return bool(amap_key and amap_key.strip())


def search_location(
    keyword: str,
    amap_key: str,
    city: str = "",
    size: int = 10,
) -> list[PlaceCandidate]:
    """
    POI 文本搜索。匹配的位置列表，高德按相关度排序。
    key 为空返回 []，API 错误返回 []（不抛异常）。
    """
    if not _has_key(amap_key):
        return []

    params: dict[str, Any] = {
        "key": amap_key.strip(),
        "keywords": keyword,
        "offset": size,
        "page": 1,
        "extensions": "base",
        "output": "JSON",
    }
    if city:
        params["city"] = city
        params["citylimit"] = "true"

    try:
        resp = request_with_retry(requests_get, POI_SEARCH_URL, params=params)
        data = resp.json()
    except Exception:
        return []

    if data.get("status") != "1":
        return []

    pois = data.get("pois") or []
    results: list[PlaceCandidate] = []
    for poi in pois:
        loc = poi.get("location", "")
        if "," not in loc:
            continue
        try:
            lng, lat = float(loc.split(",")[0]), float(loc.split(",")[1])
        except ValueError:
            continue
        results.append(PlaceCandidate(
            name=poi.get("name", "").strip(),
            address=poi.get("address", "") or poi.get("pname", ""),
            lng=lng,
            lat=lat,
        ))
    return results


def regeocode(lng: float, lat: float, amap_key: str) -> dict | None:
    """
    逆地理编码：经纬度 → 结构化地址信息。
    返回响应中的 regeocode 字段，失败返回 None。
    """
    if not _has_key(amap_key):
        return None

    params = {
        "key": amap_key.strip(),
        "location": f"{lng},{lat}",
        "extensions": "base",
        "output": "JSON",
    }
    try:
        resp = request_with_retry(requests_get, REGEOCODE_URL, params=params)
        data = resp.json()
    except Exception:
        return None

    if data.get("status") != "1":
        return None
    return data.get("regeocode")


# 避免顶层 import requests 的耦合：通过 net 模块的 session 发请求
def requests_get(url, **kwargs):
    """用独立短连接发 GET（高德 API 无 session 依赖）。"""
    import requests
    kwargs.setdefault("timeout", (5, 15))
    return requests.get(url, **kwargs)
