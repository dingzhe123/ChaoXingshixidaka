"""
路径解析 —— 全项目唯一的路径入口。

为什么不能再用 __file__：
  PyInstaller --onefile 打包后，__file__ 指向临时解包目录 _MEIPASS，
  每次运行配置都会"丢失"（读到默认值、日志写到临时目录后被删除）。
  所以必须基于 exe 所在目录定位。

使用方式：
  全项目只从本模块导入 BASE_DIR / CONFIG_PATH / LOG_DIR，
  禁止任何其他地方自行拼接 config/ 或 logs/ 路径。
"""
import os
import sys


def _resolve_base_dir() -> str:
    """返回软件根目录（config/、logs/ 所在的目录）。"""
    if getattr(sys, "frozen", False):
        # PyInstaller 打包后：sys.executable 是 exe 的完整路径
        return os.path.dirname(sys.executable)
    # 开发期：本文件在 core/，根目录是上一级
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


BASE_DIR = _resolve_base_dir()

CONFIG_PATH = os.path.join(BASE_DIR, "config", "config.json")
CONFIG_EXAMPLE_PATH = os.path.join(BASE_DIR, "config", "config.example.json")
LOG_DIR = os.path.join(BASE_DIR, "logs")


def ensure_dirs() -> tuple[bool, str]:
    """
    确保 config/ 与 logs/ 目录存在。
    返回 (ok, error_message)。
    """
    for d in (os.path.dirname(CONFIG_PATH), LOG_DIR):
        try:
            os.makedirs(d, exist_ok=True)
        except OSError as e:
            return False, f"无法创建目录 {d}：{e}"
    return True, ""


def check_writable() -> tuple[bool, str]:
    r"""
    检测软件根目录是否可写。
    若用户解压到 C:\Program Files 等受保护目录，会写不进配置。
    返回 (ok, error_message)。
    """
    # 用「创建再删除临时文件」的方式测试，比 os.access 更可靠
    probe = os.path.join(BASE_DIR, "._write_probe_tmp")
    try:
        with open(probe, "w") as f:
            f.write("ok")
        os.remove(probe)
        return True, ""
    except OSError as e:
        return False, (
            f"软件目录不可写：{BASE_DIR}\n"
            f"原因：{e}\n\n"
            f"请把整个软件文件夹移动到桌面或 D 盘等位置后重试。\n"
            "不要放在 C:\\Program Files 等受系统保护的目录中。"
        )
