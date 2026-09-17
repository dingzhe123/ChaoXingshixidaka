"""
静默入口 — 由 后台打卡.exe 构建目标引用。

【关键约束】本文件不得 import 任何 GUI 模块（PyQt5、tkinter）。
任何 GUI 的 import 都必须藏在函数里也不行——PyInstaller 静态分析
会无条件打包所有被引用的模块。

运行: python silent_main.py --type 0/1
"""
import argparse
import sys
import os

# 把项目根加入 sys.path，确保 core/ 可被导入
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.paths import BASE_DIR, check_writable, ensure_dirs


def main():
    parser = argparse.ArgumentParser(description="学习通实习打卡 — 静默模式")
    parser.add_argument("--type", choices=["0", "1"], default="0",
                        help="0=上班打卡, 1=下班打卡")
    args = parser.parse_args()

    # 目录可写性检测（D2）
    ok, err = ensure_dirs()
    if not ok:
        print(f"[silent] 目录创建失败: {err}", file=sys.stderr)
        return 2

    ok, err = check_writable()
    if not ok:
        print(f"[silent] {err}", file=sys.stderr)
        return 2

    print(f"[silent] 静默模式启动，BASE_DIR={BASE_DIR}, type={args.type}")
    print("[silent] TODO: 打卡逻辑将在 Phase 2 接入")

    # TODO Phase 2: 加载配置 -> 建 session -> 登录 -> 幂等检查 -> 打卡
    return 0


if __name__ == "__main__":
    sys.exit(main())
