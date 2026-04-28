"""
修复浏览器崩溃问题 - 优化Chrome启动参数
解决Chrome 131+版本的稳定性问题
"""
import logging
import os
import platform
import random
from selenium import webdriver
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.edge.service import Service as EdgeService
from webdriver_manager.microsoft import EdgeChromiumDriverManager


def get_stable_webdriver(driver_implicity_wait_time=60):
    """
    获取稳定的WebDriver
    修复Chrome崩溃问题
    """
    if platform.system() == 'Windows':
        # Windows使用Edge（更稳定）
        driver = webdriver.Edge(service=EdgeService(EdgeChromiumDriverManager(
            url="https://msedgedriver.microsoft.com/",
            latest_release_url="https://msedgedriver.microsoft.com/LATEST_RELEASE").install()))
        logging.info("Using Edge browser on Windows")
    else:
        # Linux使用优化的Chrome配置
        chrome_options = webdriver.ChromeOptions()

        # === 核心稳定性参数 ===
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")  # 解决共享内存不足
        chrome_options.add_argument("--disable-gpu")  # 禁用GPU加速
        chrome_options.add_argument("--disable-gpu-sandbox")  # 禁用GPU沙箱
        chrome_options.add_argument("--disable-software-rasterizer")  # 禁用软件光栅化

        # === Headless模式配置 ===
        # 优先使用Xvfb虚拟显示器（最稳定）
        if 'DISPLAY' in os.environ:
            logging.info(f"✓ 使用Xvfb虚拟显示器: {os.environ['DISPLAY']}")
            # 不添加--headless，Chrome会在Xvfb上运行（headed模式）
        else:
            # 无虚拟显示器时使用headless
            chrome_options.add_argument("--headless=new")
            logging.info("✓ 使用headless=new模式")

        # === 窗口和显示参数 ===
        chrome_options.add_argument("--window-size=1920,1080")
        chrome_options.add_argument("--start-maximized")

        # === 性能优化参数 ===
        chrome_options.add_argument("--disable-extensions")  # 禁用扩展
        chrome_options.add_argument("--disable-plugins")  # 禁用插件
        chrome_options.add_argument("--disable-images")  # 禁用图片加载（可选，提升速度）
        chrome_options.add_argument("--disable-javascript")  # 禁用JS（谨慎使用）

        # === 稳定性增强参数 ===
        chrome_options.add_argument("--disable-setuid-sandbox")
        chrome_options.add_argument("--disable-web-security")  # 禁用同源策略
        chrome_options.add_argument("--disable-features=VizDisplayCompositor")
        chrome_options.add_argument("--disable-breakpad")  # 禁用崩溃报告
        chrome_options.add_argument("--disable-client-side-phishing-detection")
        chrome_options.add_argument("--disable-sync")
        chrome_options.add_argument("--disable-translate")
        chrome_options.add_argument("--metrics-recording-only")
        chrome_options.add_argument("--no-first-run")
        chrome_options.add_argument("--safebrowsing-disable-auto-update")
        chrome_options.add_argument("--disable-background-networking")

        # === 内存优化 ===
        chrome_options.add_argument("--disable-background-timer-throttling")
        chrome_options.add_argument("--disable-backgrounding-occluded-windows")
        chrome_options.add_argument("--disable-renderer-backgrounding")
        chrome_options.add_argument("--disable-features=TranslateUI")
        chrome_options.add_argument("--disable-ipc-flooding-protection")

        # === 日志控制 ===
        chrome_options.add_argument("--log-level=3")  # 只显示严重错误
        chrome_options.add_argument("--silent")

        # === 语言设置 ===
        chrome_options.add_argument("--lang=zh-CN,zh")
        chrome_options.add_argument("--accept-lang=zh-CN,zh;q=0.9")

        # === 反检测参数 ===
        chrome_options.add_argument("--disable-blink-features=AutomationControlled")
        chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
        chrome_options.add_experimental_option("useAutomationExtension", False)

        # === 随机User-Agent ===
        ua_list = [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
        ]
        chrome_options.add_argument(f"user-agent={random.choice(ua_list)}")

        # === 实验性功能 ===
        prefs = {
            "profile.default_content_setting_values": {
                "images": 2,  # 禁用图片
                "notifications": 2,  # 禁用通知
            },
            "profile.managed_default_content_settings": {
                "images": 2
            }
        }
        chrome_options.add_experimental_option("prefs", prefs)

        # === Docker环境特殊配置 ===
        if 'PYTHON_IN_DOCKER' in os.environ:
            chrome_options.binary_location = "/opt/chrome-linux64/chrome"
            service = ChromeService(executable_path="/opt/chromedriver-linux64/chromedriver")
            logging.info("✓ Docker环境配置")
        else:
            service = ChromeService()

        # === 创建Driver ===
        driver = webdriver.Chrome(options=chrome_options, service=service)
        driver.implicitly_wait(driver_implicity_wait_time)

        # === JS级别反检测 ===
        try:
            driver.execute_script("""
                Object.defineProperty(navigator, 'webdriver', {
                    get: () => undefined
                });
            """)
            logging.info("✓ 反检测JS注入成功")
        except Exception as e:
            logging.warning(f"反检测JS注入失败: {e}")

        logging.info("✓ Chrome浏览器初始化成功")

    return driver


def diagnose_chrome_issues():
    """
    诊断Chrome崩溃问题
    """
    issues = []

    # 检查1：DISPLAY环境变量
    if 'DISPLAY' not in os.environ:
        issues.append("⚠️  未设置DISPLAY环境变量，建议使用Xvfb")
    else:
        issues.append(f"✓ DISPLAY已设置: {os.environ['DISPLAY']}")

    # 检查2：共享内存
    try:
        import subprocess
        result = subprocess.run(['df', '-h', '/dev/shm'], capture_output=True, text=True)
        if result.returncode == 0:
            issues.append(f"✓ /dev/shm状态:\n{result.stdout}")
        else:
            issues.append("⚠️  无法检查/dev/shm")
    except:
        issues.append("⚠️  无法检查/dev/shm")

    # 检查3：Chrome版本
    try:
        chrome_path = "/opt/chrome-linux64/chrome"
        if os.path.exists(chrome_path):
            result = subprocess.run([chrome_path, '--version'], capture_output=True, text=True)
            issues.append(f"✓ Chrome版本: {result.stdout.strip()}")
        else:
            issues.append("⚠️  Chrome未安装或路径错误")
    except:
        issues.append("⚠️  无法检查Chrome版本")

    # 检查4：内存
    try:
        result = subprocess.run(['free', '-h'], capture_output=True, text=True)
        if result.returncode == 0:
            issues.append(f"✓ 内存状态:\n{result.stdout}")
    except:
        pass

    return "\n".join(issues)


# 使用示例
"""
在 data_fetcher.py 中替换 _get_webdriver 方法：

from stable_webdriver import get_stable_webdriver

def _get_webdriver(self):
    return get_stable_webdriver(self.DRIVER_IMPLICITY_WAIT_TIME)
"""
