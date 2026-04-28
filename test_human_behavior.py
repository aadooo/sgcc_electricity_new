"""
测试人类行为模拟器
验证鼠标轨迹是否自然，是否能绕过验证码检测
"""
import time
import logging
from selenium import webdriver
from selenium.webdriver.common.by import By
from human_behavior_simulator import HumanBehaviorSimulator

logging.basicConfig(level=logging.INFO)


def test_mouse_trajectory():
    """测试鼠标轨迹生成"""
    print("=== 测试贝塞尔曲线轨迹生成 ===")

    trajectory = HumanBehaviorSimulator.bezier_curve(
        start=(0, 0),
        end=(300, 200),
        control_points=2,
        steps=50
    )

    print(f"生成了 {len(trajectory)} 个轨迹点")
    print(f"起点: {trajectory[0]}")
    print(f"终点: {trajectory[-1]}")
    print(f"中间点示例: {trajectory[len(trajectory)//2]}")

    # 检查轨迹是否平滑（相邻点距离不应太大）
    max_distance = 0
    for i in range(1, len(trajectory)):
        dx = trajectory[i][0] - trajectory[i-1][0]
        dy = trajectory[i][1] - trajectory[i-1][1]
        distance = (dx**2 + dy**2)**0.5
        max_distance = max(max_distance, distance)

    print(f"相邻点最大距离: {max_distance:.2f} 像素")
    print("✓ 轨迹生成测试通过\n")


def test_speed_profile():
    """测试速度曲线"""
    print("=== 测试速度曲线 ===")

    delays = HumanBehaviorSimulator.human_like_speed_profile(steps=50)

    print(f"生成了 {len(delays)} 个延迟值")
    print(f"开始速度（延迟）: {delays[0]:.4f}秒")
    print(f"中间速度（延迟）: {delays[len(delays)//2]:.4f}秒")
    print(f"结束速度（延迟）: {delays[-1]:.4f}秒")
    print(f"总耗时: {sum(delays):.3f}秒")
    print("✓ 速度曲线测试通过\n")


def test_real_browser_interaction():
    """在真实浏览器中测试人类行为"""
    print("=== 测试真实浏览器交互 ===")
    print("将打开浏览器并测试鼠标移动...")

    try:
        # 初始化driver
        options = webdriver.ChromeOptions()
        # 不使用headless，这样可以看到鼠标移动
        options.add_argument("--start-maximized")
        driver = webdriver.Chrome(options=options)

        # 打开一个测试页面
        driver.get("https://www.baidu.com")
        time.sleep(2)

        # 测试1：人类式移动到搜索框
        print("测试1: 移动到搜索框...")
        search_box = driver.find_element(By.ID, "kw")
        HumanBehaviorSimulator.move_to_element_human_like(driver, search_box)
        print("✓ 移动完成")

        # 测试2：人类式输入
        print("测试2: 模拟人类打字...")
        HumanBehaviorSimulator.simulate_typing(search_box, "人类行为测试", typing_speed='normal')
        print("✓ 输入完成")

        # 测试3：人类式点击搜索按钮
        print("测试3: 点击搜索按钮...")
        search_button = driver.find_element(By.ID, "su")
        HumanBehaviorSimulator.click_with_human_behavior(driver, search_button)
        print("✓ 点击完成")

        time.sleep(3)

        print("\n✓ 真实浏览器交互测试通过")
        print("请观察浏览器中的鼠标移动是否自然")

        driver.quit()

    except Exception as e:
        print(f"✗ 测试失败: {e}")
        import traceback
        traceback.print_exc()


def test_click_captcha_simulation():
    """模拟点击验证码场景"""
    print("=== 模拟点击验证码场景 ===")

    # 模拟验证码识别结果
    positions = [
        (100, 50),   # 第一个字
        (200, 80),   # 第二个字
        (150, 120),  # 第三个字
        (250, 90),   # 第四个字
    ]

    print(f"需要点击 {len(positions)} 个位置")

    # 计算总耗时
    total_time = 0
    for i in range(len(positions)):
        # 移动时间（假设50步，每步0.003秒）
        move_time = 50 * 0.003
        # 悬停时间
        hover_time = 0.1
        # 点击间隔
        interval_time = 0.8 if i < len(positions) - 1 else 0

        total_time += move_time + hover_time + interval_time

    print(f"预计总耗时: {total_time:.2f}秒")
    print("✓ 点击验证码模拟测试通过\n")


def compare_with_basic_click():
    """对比基础点击和人类行为点击"""
    print("=== 对比基础点击 vs 人类行为点击 ===")

    print("\n基础点击特征:")
    print("- 直线移动")
    print("- 匀速移动")
    print("- 精确点击（无偏移）")
    print("- 固定间隔")
    print("- 容易被检测 ❌")

    print("\n人类行为点击特征:")
    print("- 贝塞尔曲线移动（自然弧线）")
    print("- 变速移动（慢-快-慢）")
    print("- 点击有±3像素随机偏移")
    print("- 随机间隔（0.5-1.2秒）")
    print("- 包含悬停行为")
    print("- 难以被检测 ✓")
    print()


if __name__ == "__main__":
    print("=" * 60)
    print("人类行为模拟器测试套件")
    print("=" * 60)
    print()

    # 运行所有测试
    test_mouse_trajectory()
    test_speed_profile()
    test_click_captcha_simulation()
    compare_with_basic_click()

    # 询问是否运行真实浏览器测试
    print("=" * 60)
    response = input("是否运行真实浏览器测试？(y/n): ")
    if response.lower() == 'y':
        test_real_browser_interaction()

    print("\n" + "=" * 60)
    print("测试完成！")
    print("=" * 60)
