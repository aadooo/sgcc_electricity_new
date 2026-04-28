"""
点位顺序验证码识别模块
支持识别"按顺序点击文字"类型的验证码
"""
import logging
import time
import random
from PIL import Image
from io import BytesIO
import base64
import re

try:
    import ddddocr
    DDDDOCR_AVAILABLE = True
except ImportError:
    DDDDOCR_AVAILABLE = False
    logging.warning("ddddocr not installed, click captcha solving will not work")


class ClickCaptchaSolver:
    """点击验证码求解器（支持多种识别方案）"""

    def __init__(self, solver_type='auto'):
        """
        初始化验证码求解器

        Args:
            solver_type: 识别方案
                - 'auto': 自动选择（优先API，降级到ddddocr）
                - 'api': 仅使用第三方API
                - 'ddddocr': 仅使用ddddocr
        """
        self.solver_type = solver_type

        # 初始化ddddocr
        if DDDDOCR_AVAILABLE and solver_type in ['auto', 'ddddocr']:
            try:
                self.det = ddddocr.DdddOcr(det=True, show_ad=False)
                self.ocr = ddddocr.DdddOcr(show_ad=False)
                logging.info("ClickCaptchaSolver: ddddocr initialized")
            except Exception as e:
                self.det = None
                self.ocr = None
                logging.warning(f"ClickCaptchaSolver: ddddocr init failed: {e}")
        else:
            self.det = None
            self.ocr = None

        # 初始化API求解器
        if solver_type in ['auto', 'api']:
            try:
                from captcha_solver_api import CaptchaSolverAPI
                import os
                platform = os.getenv('CAPTCHA_SOLVER_PLATFORM', 'chaojiying')
                self.api_solver = CaptchaSolverAPI(platform=platform)
                logging.info(f"ClickCaptchaSolver: API solver initialized ({platform})")
            except Exception as e:
                self.api_solver = None
                logging.warning(f"ClickCaptchaSolver: API solver init failed: {e}")

    def solve_click_captcha(self, image_base64, target_text):
        """
        解决点击验证码（自动选择最佳方案）

        Args:
            image_base64: 验证码图片的base64编码
            target_text: 需要点击的目标文字，例如"按顺序点击：一、二、三"

        Returns:
            list: 点击坐标列表 [(x1, y1), (x2, y2), ...]
        """
        # 方案1：优先使用第三方API（识别率高）
        if self.solver_type in ['auto', 'api'] and hasattr(self, 'api_solver') and self.api_solver:
            try:
                logging.info("Trying API solver...")
                positions = self.api_solver.solve_click_captcha(image_base64, captcha_type='9004')
                if positions:
                    logging.info(f"✓ API solver succeeded: {len(positions)} positions")
                    return positions
                else:
                    logging.warning("✗ API solver returned empty result")
            except Exception as e:
                logging.warning(f"✗ API solver failed: {e}")

        # 方案2：降级到ddddocr（免费但识别率低）
        if self.solver_type in ['auto', 'ddddocr'] and self.det and self.ocr:
            try:
                logging.info("Trying ddddocr solver...")
                positions = self._solve_with_ddddocr(image_base64, target_text)
                if positions:
                    logging.info(f"✓ ddddocr solver succeeded: {len(positions)} positions")
                    return positions
                else:
                    logging.warning("✗ ddddocr solver returned empty result")
            except Exception as e:
                logging.warning(f"✗ ddddocr solver failed: {e}")

        logging.error("All captcha solvers failed")
        return []

    def _solve_with_ddddocr(self, image_base64, target_text):
        """使用ddddocr识别（原有逻辑）"""
        try:
            # 解析base64图片
            image = self._base64_to_image(image_base64)

            # 提取目标文字（例如从"按顺序点击：一、二、三"中提取["一", "二", "三"]）
            target_chars = self._extract_target_chars(target_text)
            logging.info(f"Target characters to click: {target_chars}")

            # 使用目标检测找出所有文字区域
            det_result = self.det.detection(image)
            logging.info(f"Detected {len(det_result)} text regions")

            # 对每个区域进行OCR识别
            char_positions = {}
            for bbox in det_result:
                x1, y1, x2, y2 = bbox
                # 裁剪文字区域
                char_img = image.crop((x1, y1, x2, y2))
                # OCR识别
                char = self.ocr.classification(char_img)
                # 计算中心点
                center_x = (x1 + x2) // 2
                center_y = (y1 + y2) // 2
                char_positions[char] = (center_x, center_y)
                logging.debug(f"Detected char '{char}' at ({center_x}, {center_y})")

            # 按目标顺序生成点击坐标
            click_positions = []
            for char in target_chars:
                if char in char_positions:
                    click_positions.append(char_positions[char])
                else:
                    logging.warning(f"Target char '{char}' not found in image")

            return click_positions

        except Exception as e:
            logging.error(f"Failed to solve click captcha: {e}")
            return []

    def _base64_to_image(self, base64_str):
        """将base64字符串转换为PIL Image"""
        base64_data = re.sub('^data:image/.+;base64,', '', base64_str)
        byte_data = base64.b64decode(base64_data)
        image_data = BytesIO(byte_data)
        return Image.open(image_data)

    def _extract_target_chars(self, target_text):
        """
        从提示文字中提取目标字符
        例如："按顺序点击：一、二、三" -> ["一", "二", "三"]
        """
        # 移除常见的提示词
        text = target_text.replace("按顺序点击", "").replace("请点击", "").replace("：", "").replace(":", "")
        # 分割字符（支持顿号、逗号、空格分隔）
        chars = re.split('[、，,\\s]+', text.strip())
        # 过滤空字符
        return [c for c in chars if c]

    def click_positions_on_element(self, driver, element, positions, use_human_behavior=True):
        """
        在指定元素上按顺序点击坐标

        Args:
            driver: Selenium WebDriver
            element: 要点击的元素
            positions: 点击坐标列表 [(x1, y1), (x2, y2), ...]
            use_human_behavior: 是否使用人类行为模拟（推荐）
        """
        if use_human_behavior:
            try:
                from human_behavior_simulator import HumanBehaviorSimulator
                logging.info("Using human behavior simulation for clicking")
                HumanBehaviorSimulator.click_positions_human_like(driver, element, positions)
                return
            except ImportError:
                logging.warning("HumanBehaviorSimulator not available, using basic clicking")
            except Exception as e:
                logging.warning(f"Human behavior simulation failed: {e}, falling back to basic clicking")

        # 降级方案：基础点击（不推荐，容易被检测）
        from selenium.webdriver import ActionChains

        for i, (x, y) in enumerate(positions):
            # 添加随机偏移，模拟人类点击
            offset_x = x + random.randint(-3, 3)
            offset_y = y + random.randint(-3, 3)

            # 移动到元素并点击相对坐标
            action = ActionChains(driver)
            action.move_to_element_with_offset(element, offset_x, offset_y)
            action.click()
            action.perform()

            logging.info(f"Clicked position {i+1}/{len(positions)}: ({offset_x}, {offset_y})")

            # 点击间隔，模拟人类行为
            time.sleep(random.uniform(0.3, 0.8))


class ClickCaptchaSolverAPI:
    """使用第三方API识别点击验证码（备用方案）"""

    def __init__(self, api_url=None, api_key=None):
        self.api_url = api_url
        self.api_key = api_key

    def solve_click_captcha(self, image_base64, target_text):
        """
        调用第三方API识别点击验证码

        可选的第三方服务：
        - 超级鹰 (https://www.chaojiying.com/)
        - 若快打码 (http://www.ruokuai.com/)
        - 图鉴 (http://www.ttshitu.com/)
        """
        import requests

        if not self.api_url or not self.api_key:
            logging.error("API URL or API Key not configured")
            return []

        try:
            # 这里以超级鹰为例，实际使用时需要根据具体API调整
            response = requests.post(
                self.api_url,
                json={
                    "image": image_base64,
                    "type": "click_order",  # 点击顺序类型
                    "target": target_text,
                    "api_key": self.api_key
                },
                timeout=30
            )

            if response.status_code == 200:
                result = response.json()
                positions = result.get("positions", [])
                logging.info(f"API returned {len(positions)} click positions")
                return positions
            else:
                logging.error(f"API request failed: {response.status_code}")
                return []

        except Exception as e:
            logging.error(f"Failed to call captcha API: {e}")
            return []
