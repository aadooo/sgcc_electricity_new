"""
增强版 DataFetcher - 集成反检测和新验证码识别
使用方法：将此文件中的方法替换到 data_fetcher.py 中对应的方法
"""

def _get_webdriver_enhanced(self):
    """
    增强版WebDriver获取方法
    优先使用undetected-chromedriver，失败则降级到原有方案
    """
    import os
    import logging

    # 检查是否强制使用原有方案
    use_original = os.getenv("USE_ORIGINAL_DRIVER", "false").lower() == "true"

    if not use_original:
        # 方案1：undetected-chromedriver（推荐）
        try:
            from anti_detection_driver import get_undetected_driver
            use_headless = 'DISPLAY' not in os.environ
            driver = get_undetected_driver(headless=use_headless)
            logging.info("✓ Using undetected-chromedriver (anti-detection enabled)")
            return driver
        except Exception as e:
            logging.warning(f"✗ undetected-chromedriver failed: {e}, falling back...")

        # 方案2：selenium-stealth（备用）
        try:
            from anti_detection_driver import get_stealth_driver_fallback
            use_headless = 'DISPLAY' not in os.environ
            driver = get_stealth_driver_fallback(headless=use_headless)
            logging.info("✓ Using selenium-stealth (anti-detection enabled)")
            return driver
        except Exception as e:
            logging.warning(f"✗ selenium-stealth failed: {e}, using original driver...")

    # 方案3：原有方案（增强版）
    logging.info("Using original driver with enhanced settings")
    return self._get_webdriver_original()


def _get_webdriver_original(self):
    """
    原有的driver获取方法（保持兼容性）
    这是原来的 _get_webdriver 方法，重命名以便调用
    """
    import platform
    from selenium import webdriver
    from selenium.webdriver.edge.service import Service as EdgeService
    from webdriver_manager.microsoft import EdgeChromiumDriverManager
    from selenium.webdriver.chrome.service import Service as ChromeService
    import os
    import logging
    import random

    if platform.system() == 'Windows':
        driver = webdriver.Edge(service=EdgeService(EdgeChromiumDriverManager(
            url="https://msedgedriver.microsoft.com/",
            latest_release_url="https://msedgedriver.microsoft.com/LATEST_RELEASE").install()))
    else:
        chrome_options = webdriver.ChromeOptions()

        # 如果有 Xvfb 虚拟显示器则用 headed 模式，否则 headless
        if 'DISPLAY' in os.environ:
            logging.info(f"使用 Xvfb 虚拟显示器: {os.environ['DISPLAY']}")
        else:
            chrome_options.add_argument("--headless=new")
            logging.info("无 DISPLAY，使用 headless 模式")

        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--start-maximized")
        chrome_options.add_argument("--window-size=1920,1080")

        # 增强反检测
        chrome_options.add_argument("--disable-blink-features=AutomationControlled")
        chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
        chrome_options.add_experimental_option("useAutomationExtension", False)

        # 随机User-Agent
        ua_list = [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
        ]
        chrome_options.add_argument(f"user-agent={random.choice(ua_list)}")

        chrome_options.add_argument("--disable-infobars")
        chrome_options.add_argument("--lang=zh-CN,zh")
        chrome_options.add_argument("--disable-extensions")
        chrome_options.add_argument("--log-level=3")
        chrome_options.add_argument("--silent")

        if 'PYTHON_IN_DOCKER' in os.environ:
            chrome_options.binary_location = "/opt/chrome-linux64/chrome"
            service = ChromeService(executable_path="/opt/chromedriver-linux64/chromedriver")
        else:
            service = ChromeService()

        driver = webdriver.Chrome(options=chrome_options, service=service)
        driver.implicitly_wait(self.DRIVER_IMPLICITY_WAIT_TIME)

        try:
            driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined});")
            logging.info("Anti-detection JS injected")
        except Exception as e:
            logging.warning(f"Anti-detection injection failed: {e}")

    return driver


def _handle_captcha_auto(self, driver):
    """
    自动检测并处理验证码（滑动或点击）
    返回：True表示处理成功，False表示失败或无验证码
    """
    import time
    import logging
    from selenium.webdriver.common.by import By

    time.sleep(2)  # 等待验证码加载

    # 检测验证码类型
    try:
        # 检测点击验证码
        click_captcha = driver.find_elements(By.CLASS_NAME, "click-captcha")
        if click_captcha:
            logging.info("检测到点击验证码")
            return self._handle_click_captcha(driver)

        # 检测滑动验证码
        slide_captcha = driver.find_elements(By.CLASS_NAME, "slide-verify-slider-mask-item")
        if slide_captcha:
            logging.info("检测到滑动验证码")
            return self._handle_slide_captcha(driver)

        logging.info("未检测到验证码")
        return True

    except Exception as e:
        logging.error(f"验证码检测失败: {e}")
        return False


def _handle_click_captcha(self, driver):
    """
    处理点击顺序验证码
    """
    import logging
    import time
    from selenium.webdriver.common.by import By

    try:
        # 初始化验证码求解器（如果还没有）
        if not hasattr(self, 'click_captcha_solver'):
            try:
                from click_captcha_solver import ClickCaptchaSolver
                self.click_captcha_solver = ClickCaptchaSolver()
            except Exception as e:
                logging.error(f"无法初始化点击验证码求解器: {e}")
                return False

        if not self.click_captcha_solver:
            logging.error("点击验证码求解器不可用")
            return False

        # 获取验证码图片和提示文字
        # 注意：这里的选择器需要根据实际页面调整
        captcha_img = driver.find_element(By.CLASS_NAME, "captcha-image")
        hint_text = driver.find_element(By.CLASS_NAME, "captcha-hint").text

        logging.info(f"验证码提示: {hint_text}")

        # 获取图片base64
        img_base64 = driver.execute_script(
            "return arguments[0].toDataURL('image/png');",
            captcha_img
        )

        # 识别点击位置
        positions = self.click_captcha_solver.solve_click_captcha(img_base64, hint_text)

        if not positions:
            logging.error("验证码识别失败")
            return False

        # 执行点击
        self.click_captcha_solver.click_positions_on_element(driver, captcha_img, positions)

        # 等待验证结果
        time.sleep(3)

        # 检查是否验证成功（根据实际页面调整）
        try:
            error_msg = driver.find_element(By.CLASS_NAME, "captcha-error")
            if error_msg.is_displayed():
                logging.error(f"验证码验证失败: {error_msg.text}")
                return False
        except:
            pass

        logging.info("点击验证码处理成功")
        return True

    except Exception as e:
        logging.error(f"处理点击验证码时出错: {e}")
        return False


def _handle_slide_captcha(self, driver):
    """
    处理滑动验证码（原有逻辑）
    """
    # 这里保持原有的滑动验证码处理逻辑
    # 从原来的 _login 方法中提取出来
    import logging
    logging.info("使用原有滑动验证码处理逻辑")
    # ... 原有代码 ...
    return True


# 使用示例：
"""
在 data_fetcher.py 中的修改步骤：

1. 将 _get_webdriver 方法重命名为 _get_webdriver_original
2. 添加上面的 _get_webdriver_enhanced 方法，并重命名为 _get_webdriver
3. 在 _login 方法中，输入账号密码后调用 _handle_captcha_auto

示例：
def _login(self, driver, phone_code=False):
    # ... 输入账号密码 ...

    # 自动处理验证码
    if not self._handle_captcha_auto(driver):
        logging.error("验证码处理失败")
        raise Exception("Captcha handling failed")

    # ... 继续登录流程 ...
"""
