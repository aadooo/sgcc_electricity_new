"""
人类行为模拟器 - 模拟真实的鼠标移动和点击行为
解决验证码系统的鼠标轨迹检测
"""
import time
import random
import numpy as np
from selenium.webdriver import ActionChains
from selenium.webdriver.common.actions.action_builder import ActionBuilder
from selenium.webdriver.common.actions.pointer_input import PointerInput
from selenium.webdriver.common.actions import interaction
import logging


class HumanBehaviorSimulator:
    """模拟人类鼠标行为"""

    @staticmethod
    def bezier_curve(start, end, control_points=2, steps=50):
        """
        生成贝塞尔曲线轨迹点

        Args:
            start: 起点坐标 (x, y)
            end: 终点坐标 (x, y)
            control_points: 控制点数量
            steps: 轨迹点数量

        Returns:
            list: 轨迹点列表 [(x1, y1), (x2, y2), ...]
        """
        # 生成控制点（在起点和终点之间随机偏移）
        points = [start]

        for i in range(control_points):
            # 在起点和终点之间插入控制点，添加随机偏移
            t = (i + 1) / (control_points + 1)
            x = start[0] + (end[0] - start[0]) * t
            y = start[1] + (end[1] - start[1]) * t

            # 添加随机偏移（垂直于直线方向）
            offset = random.randint(-50, 50)
            dx = end[1] - start[1]
            dy = -(end[0] - start[0])
            length = (dx**2 + dy**2)**0.5
            if length > 0:
                x += offset * dx / length
                y += offset * dy / length

            points.append((int(x), int(y)))

        points.append(end)

        # 使用贝塞尔曲线插值
        curve_points = []
        for t in np.linspace(0, 1, steps):
            point = HumanBehaviorSimulator._bezier_point(points, t)
            curve_points.append(point)

        return curve_points

    @staticmethod
    def _bezier_point(points, t):
        """计算贝塞尔曲线上的点"""
        n = len(points) - 1
        x = sum(HumanBehaviorSimulator._bernstein(n, i, t) * points[i][0]
                for i in range(n + 1))
        y = sum(HumanBehaviorSimulator._bernstein(n, i, t) * points[i][1]
                for i in range(n + 1))
        return (int(x), int(y))

    @staticmethod
    def _bernstein(n, i, t):
        """伯恩斯坦基函数"""
        from math import comb
        return comb(n, i) * (t ** i) * ((1 - t) ** (n - i))

    @staticmethod
    def human_like_speed_profile(steps):
        """
        生成人类移动速度曲线（慢-快-慢）

        Args:
            steps: 总步数

        Returns:
            list: 每步的延迟时间（秒）
        """
        delays = []
        for i in range(steps):
            # 使用正弦曲线模拟加速-减速
            progress = i / steps
            # 开始慢，中间快，结束慢
            speed_factor = np.sin(progress * np.pi)
            # 基础延迟 + 速度调整 + 随机抖动
            delay = 0.001 + (0.005 - 0.001) * (1 - speed_factor) + random.uniform(-0.001, 0.001)
            delays.append(max(0.0001, delay))  # 确保非负

        return delays

    @staticmethod
    def move_to_element_human_like(driver, element, offset_x=0, offset_y=0):
        """
        以人类方式移动鼠标到元素

        Args:
            driver: WebDriver实例
            element: 目标元素
            offset_x: X轴偏移
            offset_y: Y轴偏移
        """
        try:
            # 获取元素位置和大小
            location = element.location
            size = element.size

            # 计算目标位置（元素中心 + 偏移）
            target_x = location['x'] + size['width'] // 2 + offset_x
            target_y = location['y'] + size['height'] // 2 + offset_y

            # 获取当前鼠标位置（假设从屏幕中心开始）
            current_x = driver.execute_script("return window.innerWidth") // 2
            current_y = driver.execute_script("return window.innerHeight") // 2

            # 生成贝塞尔曲线轨迹
            trajectory = HumanBehaviorSimulator.bezier_curve(
                (current_x, current_y),
                (target_x, target_y),
                control_points=random.randint(1, 3),
                steps=random.randint(30, 50)
            )

            # 生成速度曲线
            delays = HumanBehaviorSimulator.human_like_speed_profile(len(trajectory))

            # 使用ActionChains模拟移动
            actions = ActionChains(driver)

            for i, (x, y) in enumerate(trajectory):
                if i == 0:
                    continue

                # 计算相对移动距离
                dx = x - trajectory[i-1][0]
                dy = y - trajectory[i-1][1]

                actions.move_by_offset(dx, dy)
                time.sleep(delays[i])

            actions.perform()

            # 到达目标后短暂悬停
            time.sleep(random.uniform(0.1, 0.3))

            logging.debug(f"Mouse moved to element with human-like trajectory")

        except Exception as e:
            logging.warning(f"Human-like movement failed, using direct move: {e}")
            # 降级到直接移动
            ActionChains(driver).move_to_element_with_offset(
                element, offset_x, offset_y
            ).perform()

    @staticmethod
    def click_with_human_behavior(driver, element, offset_x=0, offset_y=0):
        """
        以人类方式点击元素（包含移动、悬停、点击）

        Args:
            driver: WebDriver实例
            element: 目标元素
            offset_x: X轴偏移
            offset_y: Y轴偏移
        """
        try:
            # 1. 人类式移动到目标
            HumanBehaviorSimulator.move_to_element_human_like(
                driver, element, offset_x, offset_y
            )

            # 2. 悬停（人类在点击前会短暂停留）
            time.sleep(random.uniform(0.05, 0.15))

            # 3. 点击（添加微小的随机延迟）
            actions = ActionChains(driver)
            actions.click()
            actions.perform()

            # 4. 点击后短暂停留（人类不会立即移开）
            time.sleep(random.uniform(0.05, 0.1))

            logging.debug(f"Clicked element with human-like behavior at offset ({offset_x}, {offset_y})")

        except Exception as e:
            logging.error(f"Human-like click failed: {e}")
            raise

    @staticmethod
    def click_positions_human_like(driver, element, positions):
        """
        按顺序以人类方式点击多个位置（用于点击验证码）

        Args:
            driver: WebDriver实例
            element: 验证码图片元素
            positions: 点击位置列表 [(x1, y1), (x2, y2), ...]
        """
        for i, (x, y) in enumerate(positions):
            # 添加随机偏移（±3像素），模拟人类点击不精确
            offset_x = x + random.randint(-3, 3)
            offset_y = y + random.randint(-3, 3)

            logging.info(f"Clicking position {i+1}/{len(positions)}: ({offset_x}, {offset_y})")

            # 使用人类行为点击
            HumanBehaviorSimulator.click_with_human_behavior(
                driver, element, offset_x, offset_y
            )

            # 点击间隔（人类需要时间识别下一个目标）
            if i < len(positions) - 1:
                time.sleep(random.uniform(0.5, 1.2))

    @staticmethod
    def random_mouse_movement(driver, duration=2):
        """
        随机鼠标移动（模拟人类在思考时的鼠标晃动）

        Args:
            driver: WebDriver实例
            duration: 持续时间（秒）
        """
        try:
            actions = ActionChains(driver)
            start_time = time.time()

            while time.time() - start_time < duration:
                # 随机小幅度移动
                dx = random.randint(-20, 20)
                dy = random.randint(-20, 20)
                actions.move_by_offset(dx, dy)
                actions.perform()

                time.sleep(random.uniform(0.1, 0.3))

        except Exception as e:
            logging.debug(f"Random mouse movement: {e}")

    @staticmethod
    def simulate_reading_delay():
        """模拟人类阅读/思考延迟"""
        time.sleep(random.uniform(0.8, 2.0))

    @staticmethod
    def simulate_typing(element, text, typing_speed='normal'):
        """
        模拟人类打字（有延迟、有错误修正）

        Args:
            element: 输入框元素
            text: 要输入的文本
            typing_speed: 打字速度 ('slow', 'normal', 'fast')
        """
        speed_map = {
            'slow': (0.1, 0.3),
            'normal': (0.05, 0.15),
            'fast': (0.02, 0.08)
        }

        min_delay, max_delay = speed_map.get(typing_speed, speed_map['normal'])

        for char in text:
            element.send_keys(char)
            time.sleep(random.uniform(min_delay, max_delay))

            # 偶尔模拟打字错误和修正（5%概率）
            if random.random() < 0.05:
                element.send_keys('x')  # 错误字符
                time.sleep(random.uniform(0.1, 0.2))
                element.send_keys('\b\b')  # 删除错误字符和前一个字符
                time.sleep(random.uniform(0.1, 0.2))
                element.send_keys(char)  # 重新输入正确字符


# 使用示例
"""
from human_behavior_simulator import HumanBehaviorSimulator

# 1. 人类式点击
simulator = HumanBehaviorSimulator()
element = driver.find_element(By.ID, "submit-button")
simulator.click_with_human_behavior(driver, element)

# 2. 点击验证码（多个位置）
captcha_element = driver.find_element(By.CLASS_NAME, "captcha-image")
positions = [(100, 50), (200, 80), (150, 120)]  # 从ddddocr识别得到
simulator.click_positions_human_like(driver, captcha_element, positions)

# 3. 模拟人类打字
input_element = driver.find_element(By.ID, "username")
simulator.simulate_typing(input_element, "myusername", typing_speed='normal')
"""
