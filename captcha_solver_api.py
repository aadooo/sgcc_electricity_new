"""
第三方打码平台集成方案
识别率高，适合生产环境
"""
import requests
import base64
import time
import logging


class CaptchaSolverAPI:
    """第三方验证码识别服务"""

    def __init__(self, platform='chaojiying'):
        """
        初始化打码平台

        支持的平台：
        - chaojiying: 超级鹰 (http://www.chaojiying.com/)
        - ttshitu: 图鉴 (http://www.ttshitu.com/)
        - yescaptcha: YesCaptcha (https://yescaptcha.com/)
        """
        self.platform = platform
        self._load_config()

    def _load_config(self):
        """从环境变量加载配置"""
        import os

        if self.platform == 'chaojiying':
            self.username = os.getenv('CHAOJIYING_USERNAME')
            self.password = os.getenv('CHAOJIYING_PASSWORD')
            self.soft_id = os.getenv('CHAOJIYING_SOFT_ID', '123456')
            self.api_url = 'http://upload.chaojiying.net/Upload/Processing.php'

        elif self.platform == 'ttshitu':
            self.username = os.getenv('TTSHITU_USERNAME')
            self.password = os.getenv('TTSHITU_PASSWORD')
            self.api_url = 'http://api.ttshitu.com/predict'

        elif self.platform == 'yescaptcha':
            self.api_key = os.getenv('YESCAPTCHA_API_KEY')
            self.api_url = 'https://api.yescaptcha.com/createTask'

    def solve_click_captcha(self, image_base64, captcha_type='9004'):
        """
        识别点击验证码

        Args:
            image_base64: 验证码图片base64
            captcha_type: 验证码类型
                - 9004: 点击文字（按顺序）
                - 9005: 点击图标（按顺序）

        Returns:
            list: 点击坐标 [(x1, y1), (x2, y2), ...]
        """
        if self.platform == 'chaojiying':
            return self._solve_chaojiying(image_base64, captcha_type)
        elif self.platform == 'ttshitu':
            return self._solve_ttshitu(image_base64, captcha_type)
        elif self.platform == 'yescaptcha':
            return self._solve_yescaptcha(image_base64, captcha_type)
        else:
            raise ValueError(f"Unsupported platform: {self.platform}")

    def _solve_chaojiying(self, image_base64, captcha_type):
        """超级鹰识别"""
        try:
            # 移除base64前缀
            if 'base64,' in image_base64:
                image_base64 = image_base64.split('base64,')[1]

            # 构造请求
            data = {
                'user': self.username,
                'pass2': self.password,
                'softid': self.soft_id,
                'codetype': captcha_type,
                'file_base64': image_base64,
            }

            response = requests.post(self.api_url, data=data, timeout=30)
            result = response.json()

            if result['err_no'] == 0:
                # 解析坐标 "123,45|234,56|345,67"
                pic_str = result['pic_str']
                positions = []
                for coord in pic_str.split('|'):
                    x, y = map(int, coord.split(','))
                    positions.append((x, y))

                logging.info(f"超级鹰识别成功: {len(positions)}个点位")
                return positions
            else:
                logging.error(f"超级鹰识别失败: {result['err_str']}")
                return []

        except Exception as e:
            logging.error(f"超级鹰API调用失败: {e}")
            return []

    def _solve_ttshitu(self, image_base64, captcha_type):
        """图鉴识别"""
        try:
            if 'base64,' in image_base64:
                image_base64 = image_base64.split('base64,')[1]

            data = {
                'username': self.username,
                'password': self.password,
                'typeid': captcha_type,
                'image': image_base64,
            }

            response = requests.post(self.api_url, json=data, timeout=30)
            result = response.json()

            if result['success']:
                # 解析坐标
                data = result['data']
                positions = []
                for item in data['result'].split('|'):
                    x, y = map(int, item.split(','))
                    positions.append((x, y))

                logging.info(f"图鉴识别成功: {len(positions)}个点位")
                return positions
            else:
                logging.error(f"图鉴识别失败: {result['message']}")
                return []

        except Exception as e:
            logging.error(f"图鉴API调用失败: {e}")
            return []

    def _solve_yescaptcha(self, image_base64, captcha_type):
        """YesCaptcha识别"""
        try:
            data = {
                'clientKey': self.api_key,
                'task': {
                    'type': 'ImageToTextTask',
                    'body': image_base64,
                }
            }

            # 创建任务
            response = requests.post(self.api_url, json=data, timeout=30)
            result = response.json()

            if result['errorId'] == 0:
                task_id = result['taskId']

                # 轮询结果
                for _ in range(30):
                    time.sleep(2)
                    result_url = 'https://api.yescaptcha.com/getTaskResult'
                    result_data = {
                        'clientKey': self.api_key,
                        'taskId': task_id
                    }

                    result_response = requests.post(result_url, json=result_data, timeout=30)
                    result_json = result_response.json()

                    if result_json['status'] == 'ready':
                        # 解析坐标
                        solution = result_json['solution']['text']
                        positions = []
                        for coord in solution.split('|'):
                            x, y = map(int, coord.split(','))
                            positions.append((x, y))

                        logging.info(f"YesCaptcha识别成功: {len(positions)}个点位")
                        return positions

                logging.error("YesCaptcha识别超时")
                return []
            else:
                logging.error(f"YesCaptcha识别失败: {result['errorDescription']}")
                return []

        except Exception as e:
            logging.error(f"YesCaptcha API调用失败: {e}")
            return []


# 使用示例
"""
# 1. 配置环境变量（.env文件）
CAPTCHA_SOLVER_PLATFORM=chaojiying
CHAOJIYING_USERNAME=your_username
CHAOJIYING_PASSWORD=your_password
CHAOJIYING_SOFT_ID=123456

# 2. 使用
from captcha_solver_api import CaptchaSolverAPI

solver = CaptchaSolverAPI(platform='chaojiying')
positions = solver.solve_click_captcha(image_base64, captcha_type='9004')

if positions:
    # 使用人类行为模拟器点击
    from human_behavior_simulator import HumanBehaviorSimulator
    HumanBehaviorSimulator.click_positions_human_like(driver, element, positions)
"""
