"""
反检测WebDriver封装
使用undetected-chromedriver绕过国家电网的反爬检测
"""
import logging
import os
import random
import undetected_chromedriver as uc
from selenium.webdriver.chrome.options import Options

def get_undetected_driver(headless=True):
    """
    获取反检测的Chrome Driver

    Args:
        headless: 是否使用无头模式

    Returns:
        undetected_chromedriver实例
    """
    options = uc.ChromeOptions()

    # 基础参数
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--window-size=1920,1080")
    options.add_argument("--start-maximized")

    # 语言和地区
    options.add_argument("--lang=zh-CN,zh")
    options.add_argument("--accept-lang=zh-CN,zh;q=0.9")

    # 禁用一些可能暴露自动化的功能
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument("--disable-infobars")
    options.add_argument("--log-level=3")

    # 随机User-Agent（使用最新版本）
    ua_list = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    ]
    options.add_argument(f"user-agent={random.choice(ua_list)}")

    # Headless模式（undetected-chromedriver的headless更难被检测）
    if headless:
        options.add_argument("--headless=new")
        # 在headless模式下设置合理的窗口大小
        options.add_argument("--window-size=1920,1080")

    # Docker环境特殊配置
    if 'PYTHON_IN_DOCKER' in os.environ:
        options.binary_location = "/opt/chrome-linux64/chrome"
        driver_executable_path = "/opt/chromedriver-linux64/chromedriver"
    else:
        driver_executable_path = None

    try:
        # undetected_chromedriver会自动处理很多反检测特征
        driver = uc.Chrome(
            options=options,
            driver_executable_path=driver_executable_path,
            version_main=None,  # 自动检测Chrome版本
            use_subprocess=True,  # 使用子进程模式，更稳定
        )

        # 设置隐式等待
        driver.implicitly_wait(60)

        # 额外的JS注入（增强反检测）
        driver.execute_cdp_cmd('Page.addScriptToEvaluateOnNewDocument', {
            'source': '''
                // 覆盖webdriver属性
                Object.defineProperty(navigator, 'webdriver', {
                    get: () => undefined
                });

                // 覆盖plugins
                Object.defineProperty(navigator, 'plugins', {
                    get: () => [1, 2, 3, 4, 5]
                });

                // 覆盖languages
                Object.defineProperty(navigator, 'languages', {
                    get: () => ['zh-CN', 'zh', 'en']
                });

                // 伪造Chrome对象
                window.chrome = {
                    runtime: {}
                };

                // 覆盖permissions
                const originalQuery = window.navigator.permissions.query;
                window.navigator.permissions.query = (parameters) => (
                    parameters.name === 'notifications' ?
                        Promise.resolve({ state: Notification.permission }) :
                        originalQuery(parameters)
                );
            '''
        })

        logging.info("Undetected ChromeDriver initialized successfully.")
        return driver

    except Exception as e:
        logging.error(f"Failed to initialize undetected driver: {e}")
        raise


def get_stealth_driver_fallback(headless=True):
    """
    备用方案：使用selenium + stealth插件
    如果undetected-chromedriver不可用，使用这个方案
    """
    from selenium import webdriver
    from selenium.webdriver.chrome.service import Service as ChromeService
    from selenium_stealth import stealth

    chrome_options = webdriver.ChromeOptions()

    # 基础参数
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--window-size=1920,1080")

    if headless:
        chrome_options.add_argument("--headless=new")

    # 反检测参数
    chrome_options.add_argument("--disable-blink-features=AutomationControlled")
    chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
    chrome_options.add_experimental_option("useAutomationExtension", False)

    # User-Agent
    ua = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
    chrome_options.add_argument(f"user-agent={ua}")

    # Docker环境
    if 'PYTHON_IN_DOCKER' in os.environ:
        chrome_options.binary_location = "/opt/chrome-linux64/chrome"
        service = ChromeService(executable_path="/opt/chromedriver-linux64/chromedriver")
    else:
        service = ChromeService()

    driver = webdriver.Chrome(options=chrome_options, service=service)

    # 应用stealth插件
    stealth(driver,
        languages=["zh-CN", "zh", "en-US", "en"],
        vendor="Google Inc.",
        platform="Win32",
        webgl_vendor="Intel Inc.",
        renderer="Intel Iris OpenGL Engine",
        fix_hairline=True,
    )

    driver.implicitly_wait(60)
    logging.info("Stealth ChromeDriver initialized successfully.")
    return driver
