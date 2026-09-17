"""
学习通实习打卡 — 连接性测试脚本
只调用读接口，不执行任何打卡操作，用于验证账号和接口是否有效。
"""
import requests

# ========== 配置（填写你的信息） ==========
username = ""       # 手机号或学号
password = ""       # 密码
schoolid = ""       # 学校ID（学号登录时必填，手机号登录时留空）
# ===========================================

headers = {
    'User-Agent': 'Mozilla/5.0 (Linux; Android 12; Redmi K30 Pro Zoom Edition Build/SKQ1.211006.001; wv) AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/95.0.4638.74 Mobile Safari/537.36 (device:Redmi K30 Pro Zoom Edition) Language/zh_CN com.chaoxing.mobile/ChaoXingStudy_3_6.2.8_android_phone_1050_234 (@Kalimdor)_8c0587fc07ee4c25bdbbb5d7a90d8152'
}

def check(name, condition, ok_msg="", fail_msg=""):
    """打印检查结果"""
    if condition:
        print(f"  ✅ {name}: {ok_msg}")
    else:
        print(f"  ❌ {name}: {fail_msg}")
    return condition


def test_login(session):
    """测试 1: 登录"""
    print("\n[1/5] 测试登录...")
    url = f"https://passport2.chaoxing.com/api/login?name={username}&pwd={password}&password={password}&schoolid={schoolid}&verify=0"
    try:
        res = session.post(url, headers=headers, timeout=10)
        data = res.json()
        if data.get("result"):
            check("登录状态", True, "登录成功")
            return True
        else:
            check("登录状态", False, fail_msg=f"登录失败 — {data.get('errorMsg', data)}")
            return False
    except requests.exceptions.Timeout:
        check("登录状态", False, fail_msg="请求超时（10s），网络可能不通")
        return False
    except Exception as e:
        check("登录状态", False, fail_msg=f"异常: {e}")
        return False


def test_my_plan_list(session):
    """测试 2: 获取实习计划列表"""
    print("\n[2/5] 获取新版实习计划列表...")
    url = "https://sx.chaoxing.com/internship/planUser/myPlanList"
    try:
        res = session.get(url, headers=headers, timeout=10)
        if res.url != url:
            check("接口状态", False, fail_msg="被重定向，session 可能失效")
            return None
        data = res.json()
        if data.get("result") == 0 and data.get("data"):
            plans = data["data"]
            check("接口状态", True, f"找到 {len(plans)} 个实习计划")
            for i, p in enumerate(plans, 1):
                status_map = {1: "进行中", 2: "已结束", 3: "未开始"}
                print(f"     计划{i}: {p.get('planName', 'N/A')} [{status_map.get(p.get('planStatus'), '?')}]")
            return plans
        elif data.get("result") == 0:
            check("接口状态", False, fail_msg="当前没有实习计划（接口正常，但无数据）")
            return []
        else:
            check("接口状态", False, fail_msg=data.get("errorMsg", "未知错误"))
            return None
    except Exception as e:
        check("接口状态", False, fail_msg=f"异常: {e}")
        return None


def test_clockin_config(session, plans):
    """测试 3: 获取打卡配置"""
    if not plans:
        print("\n[3/5] 跳过打卡配置检查（无实习计划）")
        return
    print("\n[3/5] 获取打卡配置...")
    plan = plans[0]
    plan_id = plan["planId"]
    url = f"https://sx.chaoxing.com/internship/dgsxpc/{plan_id}"
    try:
        res = session.get(url, headers=headers, timeout=10)
        if res.url != url:
            check("接口状态", False, fail_msg="被重定向")
            return
        data = res.json()
        if data.get("result") == 0 and data.get("data"):
            cfg = data["data"]
            check("接口状态", True,
                  f"实时签到={'是' if cfg.get('isontimesign') else '否'}, 偏移量={cfg.get('offset', 'N/A')}米")
        else:
            check("接口状态", False, fail_msg=data.get("errorMsg", "未知错误"))
    except Exception as e:
        check("接口状态", False, fail_msg=f"异常: {e}")


def test_today_record(session, plans):
    """测试 4: 获取今日打卡记录"""
    import time
    if not plans:
        print("\n[4/5] 跳过今日打卡记录检查（无实习计划）")
        return
    print("\n[4/5] 获取今日打卡记录...")
    plan = plans[0]
    plan_id = plan["planId"]
    today = time.strftime("%Y-%m-%d")
    url = f"https://sx.chaoxing.com/internship/clockin-user/get/stu/{plan_id}/date?date={today}"
    try:
        res = session.get(url, headers=headers, timeout=10)
        if res.url != url:
            check("接口状态", False, fail_msg="被重定向")
            return
        data = res.json()
        if data.get("result") == 0 and data.get("data"):
            rec = data["data"]
            check("接口状态", True,
                  f"clockinId={rec.get('id', 'N/A')}, recruitId={rec.get('recruitId', 'N/A')}")
        elif data.get("result") == 0:
            check("接口状态", False, fail_msg="今日无打卡记录（接口正常）")
        else:
            check("接口状态", False, fail_msg=data.get("errorMsg", "未知错误"))
    except Exception as e:
        check("接口状态", False, fail_msg=f"异常: {e}")


def test_user_org(session):
    """测试 5: 获取用户学校站点（旧版打卡用）"""
    print("\n[5/5] 获取用户学校站点信息...")
    url = "https://i.chaoxing.com/base/cacheUserOrg"
    try:
        res = session.get(url, headers=headers, timeout=10)
        data = res.json()
        sites = data.get("site", [])
        check("接口状态", True, f"找到 {len(sites)} 个站点")
        for s in sites:
            print(f"     站点: fid={s.get('fid', 'N/A')}, name={s.get('name', 'N/A')}")
    except Exception as e:
        check("接口状态", False, fail_msg=f"异常: {e}")


def main():
    print("=" * 50)
    print("  学习通实习打卡 — 连接性测试")
    print("  （只读接口，不会执行打卡操作）")
    print("=" * 50)

    if not username or not password:
        print("\n❌ 请先在脚本中填写 username 和 password")
        return

    session = requests.Session()

    # 测试 1: 登录
    if not test_login(session):
        print("\n登录失败，后续测试跳过。请检查账号密码。")
        return

    # 测试 2: 实习计划列表
    plans = test_my_plan_list(session)

    # 测试 3: 打卡配置
    test_clockin_config(session, plans)

    # 测试 4: 今日打卡记录
    test_today_record(session, plans)

    # 测试 5: 用户站点
    test_user_org(session)

    print("\n" + "=" * 50)
    print("  测试完成")
    print("=" * 50)


if __name__ == "__main__":
    main()
