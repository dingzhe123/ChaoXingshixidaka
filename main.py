"""
GUI 入口 — 由 打卡助手.exe 构建目标引用。
本文件顶部会 import PyQt5，因此绝不能被 silent_main.py 导入。

运行: python main.py
"""
import sys
import os

# 把项目根加入 sys.path，确保 core/ 可被导入
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from PyQt5.QtWidgets import QApplication, QMainWindow, QLabel, QVBoxLayout, QWidget


def main():
    app = QApplication(sys.argv)
    window = QMainWindow()
    window.setWindowTitle("学习通实习打卡助手")
    window.resize(600, 400)

    central = QWidget()
    layout = QVBoxLayout(central)
    layout.addWidget(QLabel("TODO: GUI 将在 Phase 3 实现"))
    layout.addWidget(QLabel("当前仅验证打包流程"))
    window.setCentralWidget(central)

    window.show()
    return app.exec_()


if __name__ == "__main__":
    sys.exit(main())
