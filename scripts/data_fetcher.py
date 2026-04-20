import logging
import os
import re
import time

import random
import base64
from datetime import datetime
from selenium import webdriver
from selenium.webdriver import ActionChains
from selenium.webdriver.edge.service import Service as EdgeService
from webdriver_manager.microsoft import EdgeChromiumDriverManager
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.wait import WebDriverWait
from sensor_updator import SensorUpdator
from error_watcher import ErrorWatcher
from typing import Optional

from const import *

import numpy as np
# import cv2
from io import BytesIO
from PIL import Image
from onnx import ONNX
import platform


def base64_to_PLI(base64_str: str):
    base64_data = re.sub('^data:image/.+;base64,', '', base64_str)
    byte_data = base64.b64decode(base64_data)
    image_data = BytesIO(byte_data)
    img = Image.open(image_data)
    return img

def get_transparency_location(image):
    '''获取基于透明元素裁切图片的左上角、右下角坐标

    :param image: cv2加载好的图像
    :return: (left, upper, right, lower)元组
    '''
    # 1. 扫描获得最左边透明点和最右边透明点坐标
    height, width, channel = image.shape  # 高、宽、通道数
    assert channel == 4  # 无透明通道报错
    first_location = None  # 最先遇到的透明点
    last_location = None  # 最后遇到的透明点
    first_transparency = []  # 从左往右最先遇到的透明点，元素个数小于等于图像高度
    last_transparency = []  # 从左往右最后遇到的透明点，元素个数小于等于图像高度
    for y, rows in enumerate(image):
        for x, BGRA in enumerate(rows):
            alpha = BGRA[3]
            if alpha != 0:
                if not first_location or first_location[1] != y:  # 透明点未赋值或为同一列
                    first_location = (x, y)  # 更新最先遇到的透明点
                    first_transparency.append(first_location)
                last_location = (x, y)  # 更新最后遇到的透明点
        if last_location:
            last_transparency.append(last_location)

    # 2. 矩形四个边的中点
    top = first_transparency[0]
    bottom = first_transparency[-1]
    left = None
    right = None
    for first, last in zip(first_transparency, last_transparency):
        if not left:
            left = first
        if not right:
            right = last
        if first[0] < left[0]:
            left = first
        if last[0] > right[0]:
            right = last

    # 3. 左上角、右下角
    upper_left = (left[0], top[1])  # 左上角
    bottom_right = (right[0], bottom[1])  # 右下角

    return upper_left[0], upper_left[1], bottom_right[0], bottom_right[1]

class DataFetcher:

    def __init__(self, username: str, password: str):
        if 'PYTHON_IN_DOCKER' not in os.environ: 
            import dotenv
            dotenv.load_dotenv(verbose=True)
        self._username = username
        self._password = password
        self.onnx = ONNX("./captcha.onnx")

        self.DRIVER_IMPLICITY_WAIT_TIME = int(os.getenv("DRIVER_IMPLICITY_WAIT_TIME", 60))
        self.RETRY_TIMES_LIMIT = int(os.getenv("RETRY_TIMES_LIMIT", 5))
        self.LOGIN_EXPECTED_TIME = int(os.getenv("LOGIN_EXPECTED_TIME", 10))
        self.RETRY_WAIT_TIME_OFFSET_UNIT = int(os.getenv("RETRY_WAIT_TIME_OFFSET_UNIT", 10))
        self.IGNORE_USER_ID = os.getenv("IGNORE_USER_ID", "xxxxx,xxxxx").split(",")
        self.QR_CODE_LOGIN_WAIT_COUNT = int(os.getenv("QR_CODE_LOGIN_WAIT_COUNT", 7))
        self.QR_CODE_LOGIN_WAIT_TIME_INTERVAL_UNIT = int(os.getenv("QR_CODE_LOGIN_WAIT_TIME_INTERVAL_UNIT", 10))
        self._init_db()
    
    def _init_db(self):
        self.db_type = os.getenv("DB_TYPE", "None").lower()
        if self.db_type == 'mysql':
            from db import MysqlDB
            self.db = MysqlDB()
            logging.info("Using MySQL database to store data.")
        elif self.db_type == 'sqlite':
            from db import SqliteDB
            self.db = SqliteDB()
            logging.info("Using Sqlite database to store data.")
        else:
            self.db = None
            logging.info("No database will be used to store data.")

    # @staticmethod
    def _click_button(self, driver, button_search_type, button_search_key):
        '''wrapped click function, click only when the element is clickable'''
        click_element = driver.find_element(button_search_type, button_search_key)
        # logging.info(f"click_element:{button_search_key}.is_displayed() = {click_element.is_displayed()}\r")
        # logging.info(f"click_element:{button_search_key}.is_enabled() = {click_element.is_enabled()}\r")
        WebDriverWait(driver, self.DRIVER_IMPLICITY_WAIT_TIME).until(EC.element_to_be_clickable(click_element))
        driver.execute_script("arguments[0].click();", click_element)

    # @staticmethod
    def _is_captcha_legal(self, captcha):
        ''' check the ddddocr result, justify whether it's legal'''
        if (len(captcha) != 4):
            return False
        for s in captcha:
            if (not s.isalpha() and not s.isdigit()):
                return False
        return True

    def _sliding_track(self, driver, distance):
        """Human-like sliding with acceleration curve matching real mouse movement"""
        slider = driver.find_element(By.CLASS_NAME, "slide-verify-slider-mask-item")
        ActionChains(driver).click_and_hold(slider).perform()
        
        # 初始停顿
        time.sleep(random.uniform(0.3, 0.7))

        moved = 0
        # 使用加速度曲线：慢-快-慢，更像人类鼠标移动
        # 参考：ease-out 曲线，前期快后期慢
        
        while moved < distance:
            remaining = distance - moved
            progress = moved / distance if distance > 0 else 1
            
            # 根据进度计算步进：开始快，结尾慢
            if progress < 0.3:
                # 起步加速
                step = random.randint(8, 15)
            elif progress < 0.7:
                # 中间匀速偏快
                step = random.randint(5, 12)
            elif progress < 0.9:
                # 接近目标减速
                step = random.randint(3, 6)
            else:
                # 最后微调
                step = random.randint(1, 3)
            
            step = min(step, remaining)
            if step <= 0:
                break
            
            # y轴小幅度随机偏移（模拟手抖）
            y_jitter = random.uniform(-2, 2)
            
            ActionChains(driver).move_by_offset(xoffset=step, yoffset=y_jitter).perform()
            moved += step
            
            # 延迟：越接近目标越慢
            if progress < 0.5:
                delay = random.uniform(0.01, 0.03)
            else:
                delay = random.uniform(0.02, 0.06)
            time.sleep(delay)

        logging.info(f"Sliding completed for {distance}px, moved={moved}")
        
        # 到达后短暂停顿（人类反应时间）
        time.sleep(random.uniform(0.05, 0.15))
        
        # 微小回弹（2-5px）
        rebound = random.randint(2, 5)
        ActionChains(driver).move_by_offset(xoffset=-rebound, yoffset=0).perform()
        time.sleep(random.uniform(0.03, 0.08))
        
        # 释放
        ActionChains(driver).release().perform()
        time.sleep(random.uniform(0.15, 0.3))

    def insert_expand_data(self, data:dict):
        self.db.insert_expand_data(data)
                
    def _get_webdriver(self):
        if platform.system() == 'Windows':
            driver = webdriver.Edge(service=EdgeService(EdgeChromiumDriverManager(
            url="https://msedgedriver.microsoft.com/",
            latest_release_url="https://msedgedriver.microsoft.com/LATEST_RELEASE").install()))
        else:
            chrome_options = webdriver.ChromeOptions()

            # 如果有 DISPLAY 环境变量（xvfb 模式），不使用 headless
            if os.environ.get('DISPLAY'):
                logging.info("Using Xvfb virtual display (non-headless mode).\\r")
                # 不加 --headless，让 Chrome 在虚拟显示器上运行
            else:
                chrome_options.add_argument("--headless=new")

            chrome_options.add_argument("--no-sandbox")
            chrome_options.add_argument("--disable-gpu")
            chrome_options.add_argument("--disable-dev-shm-usage")
            chrome_options.add_argument("--start-maximized")
            chrome_options.add_argument("--window-size=1920,1080")

            # --- 规避反爬 ---
            chrome_options.add_argument("--disable-blink-features=AutomationControlled")
            chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
            chrome_options.add_experimental_option("useAutomationExtension", False)

            # 随机化 user-agent，模拟真实浏览器
            ua_list = [
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
                "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
            ]
            chrome_options.add_argument(f"user-agent={random.choice(ua_list)}")

            # 额外反检测参数
            chrome_options.add_argument("--disable-infobars")
            chrome_options.add_argument("--lang=zh-CN,zh")
            chrome_options.add_argument("--disable-extensions")
            chrome_options.add_argument("--log-level=3")
            chrome_options.add_argument("--silent")

            # 指定 chromium 和 chromedriver 的路径
            if 'PYTHON_IN_DOCKER' in os.environ:
                chrome_options.binary_location = "/usr/bin/chromium"
                service = ChromeService(executable_path="/usr/bin/chromedriver")
            else:
                service = ChromeService()

            driver = webdriver.Chrome(
                options=chrome_options,
                service=service,
            )
            driver.implicitly_wait(self.DRIVER_IMPLICITY_WAIT_TIME)

            # --- CDP 级别反检测：覆写 navigator.webdriver 等属性 ---
            try:
                driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
                    "source": """
                        // 覆写 webdriver 属性（最关键）
                        Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
                        // 覆写 languages
                        try { Object.defineProperty(navigator, 'languages', {get: () => ['zh-CN', 'zh', 'en']}); } catch(e) {}
                        // 覆写 permissions
                        try {
                            const origQuery = window.navigator.permissions.query;
                            window.navigator.permissions.query = (p) =>
                                p.name === 'notifications' ? Promise.resolve({state: Notification.permission}) : origQuery(p);
                        } catch(e) {}
                    """
                })
                logging.info("CDP anti-detection scripts injected.\\r")
            except Exception as e:
                logging.warning(f"Failed to inject CDP anti-detection: {e}\\r")
        return driver

    @ErrorWatcher.watch
    def _login(self, driver, phone_code = False):
        # 随机延迟，模拟人类行为
        time.sleep(random.uniform(2, 5))
        
        try:
            driver.get(LOGIN_URL)
            WebDriverWait(driver, self.DRIVER_IMPLICITY_WAIT_TIME * 3).until(EC.visibility_of_element_located((By.CLASS_NAME, "user")))
        except:
            logging.debug(f"Login failed, open URL: {LOGIN_URL} failed.")
        logging.info(f"Open LOGIN_URL:{LOGIN_URL}.\r")
        time.sleep(self.RETRY_WAIT_TIME_OFFSET_UNIT*2 + random.uniform(1, 3))
        # swtich to username-password login page
        # 临时关闭隐式等待，避免与 WebDriverWait 叠加导致超时
        driver.implicitly_wait(0)
        try:
            WebDriverWait(driver, 10).until(
                EC.invisibility_of_element_located((By.CLASS_NAME, 'el-loading-mask')))
        finally:
            driver.implicitly_wait(self.DRIVER_IMPLICITY_WAIT_TIME)  # 恢复隐式等待

        # 先关闭可能弹出的同意协议弹窗（.modal-container）
        try:
            modal_buttons = driver.find_elements(By.CSS_SELECTOR, '.modal-container button')
            for btn in modal_buttons:
                if '同意' in btn.text:
                    driver.execute_script("arguments[0].click();", btn)
                    logging.info("Dismissed agreement modal.\r")
                    time.sleep(1)
                    break
        except Exception as e:
            logging.debug(f"No modal to dismiss or dismiss failed: {e}")

        # 切换到密码登录 — Vue.js SPA需要调用组件方法而非DOM点击
        # 先尝试用Vue组件的userLoginClick方法
        switched = driver.execute_script("""
            var allEls = document.querySelectorAll('*');
            for (var i = 0; i < allEls.length; i++) {
                if (allEls[i].__vue__ && allEls[i].__vue__.$options.methods && allEls[i].__vue__.$options.methods.userLoginClick) {
                    allEls[i].__vue__.userLoginClick();
                    return true;
                }
            }
            return false;
        """)
        if switched:
            logging.info("Switched to password login via Vue userLoginClick().\r")
        else:
            # 备用方案：直接点击.switchs.sweepCode元素
            logging.warning("Vue userLoginClick not found, trying direct element click.\r")
            try:
                switch_el = driver.find_element(By.CSS_SELECTOR, '.ewm-login .login_ewm .switch .switchs.sweepCode')
                driver.execute_script("arguments[0].click();", switch_el)
                logging.info("Clicked .switchs.sweepCode directly.\r")
            except Exception as e:
                logging.warning(f"Direct click also failed: {e}, trying XPATH fallback.")
                try:
                    login_switch = driver.find_element(By.XPATH, "//div[contains(@class, 'ewm-login')]//div[contains(@class, 'switch')]//div[contains(@class, 'switchs')]")
                    driver.execute_script("arguments[0].click();", login_switch)
                    logging.info("Clicked switch via XPATH fallback.\r")
                except:
                    logging.error("Failed to find any login switch element")
        
        # 等待登录表单可见（.account-login 从 display:none 变为可见）
        try:
            WebDriverWait(driver, 15).until(
                EC.visibility_of_element_located((By.CSS_SELECTOR, '.account-login')))
            logging.info("Login form is now visible.\r")
        except Exception as e:
            logging.warning(f"Login form not visible after 15s: {e}")
            # 再次调用Vue方法切换到密码登录
            try:
                driver.execute_script("""
                    var allEls = document.querySelectorAll('*');
                    for (var i = 0; i < allEls.length; i++) {
                        if (allEls[i].__vue__ && allEls[i].__vue__.$options.methods && allEls[i].__vue__.$options.methods.userLoginClick) {
                            allEls[i].__vue__.userLoginClick();
                            break;
                        }
                    }
                """)
                logging.info("Re-called Vue userLoginClick().\r")
                time.sleep(2)
                WebDriverWait(driver, 10).until(
                    EC.visibility_of_element_located((By.CSS_SELECTOR, '.account-login')))
                logging.info("Login form visible after Vue method re-call.\r")
            except Exception as e2:
                logging.warning(f"Login form still not visible: {e2}")
                # 最后尝试直接检查密码表单
                try:
                    pwd_form = driver.find_element(By.CSS_SELECTOR, '.password_form')
                    if pwd_form and pwd_form.is_displayed():
                        logging.info("Password form is displayed directly.\r")
                    else:
                        logging.error("Password form exists but is hidden, aborting login.")
                        return False
                except:
                    logging.error("Cannot find login form at all.")
                    return False
        time.sleep(random.uniform(0.5, 1.5))
        
        # 确保切换到"密码登录"标签
        try:
            pwd_tab = driver.find_element(By.CSS_SELECTOR, '.password_login.switchs')
            driver.execute_script("arguments[0].click();", pwd_tab)
            time.sleep(random.uniform(0.3, 0.8))
        except:
            pass  # 可能已经是密码登录模式
        
        # 勾选"同意协议"复选框 — 实际元素是 .checked-box.un-checked
        # 在密码登录表单中找（data-v-118eba9d 前缀的是密码表单）
        try:
            checkbox = driver.find_element(By.CSS_SELECTOR, '.password_form .checked-box.un-checked')
            driver.execute_script("arguments[0].click();", checkbox)
            logging.info("Clicked agree checkbox (.checked-box.un-checked).\r")
        except Exception as e:
            logging.warning(f"Failed to click agree checkbox: {e}, trying alternative selector.")
            # 备用方案：点击包含"同意"文字的 span 的父元素
            try:
                book_span = driver.find_element(By.CSS_SELECTOR, '.password_form .book')
                driver.execute_script("arguments[0].click();", book_span)
                logging.info("Clicked book span as fallback.\r")
            except:
                logging.warning("All agree checkbox selectors failed.")
        
        time.sleep(random.uniform(0.3, 0.8))
        
        if phone_code:
            self._click_button(driver, By.XPATH, '//*[@id="login_box"]/div[1]/div[1]/div[3]/span')
            input_elements = driver.find_elements(By.CLASS_NAME, "el-input__inner")
            input_elements[2].send_keys(self._username)
            logging.info(f"input_elements username : {self._username}\r")
            self._click_button(driver, By.XPATH, '//*[@id="login_box"]/div[2]/div[2]/form/div[1]/div[2]/div[2]/div/a')
            code = input("Input your phone verification code: ")
            input_elements[3].send_keys(code)
            logging.info(f"input_elements verification code: {code}.\r")
            # click login button
            self._click_button(driver, By.XPATH, '//*[@id="login_box"]/div[2]/div[2]/form/div[2]/div/button/span')
            time.sleep(self.RETRY_WAIT_TIME_OFFSET_UNIT*2)
            logging.info("Click login button.\r")

            return True
        # 增加判空校验便于测试fallback
        elif self._password is not None and len(self._password) > 0:
            # 在密码登录表单中找输入框（.password_form 内的 .el-input__inner）
            pwd_form = driver.find_element(By.CSS_SELECTOR, '.password_form')
            input_elements = pwd_form.find_elements(By.CSS_SELECTOR, '.el-input__inner')
            
            # 模拟人类输入：逐字符输入用户名
            for char in self._username:
                input_elements[0].send_keys(char)
                time.sleep(random.uniform(0.05, 0.15))
            logging.info(f"input_elements username : {self._username}\r")
            
            time.sleep(random.uniform(0.5, 1.5))  # 输入用户名后等待
           
            # 模拟人类输入：逐字符输入密码
            for char in self._password:
                input_elements[1].send_keys(char)
                time.sleep(random.uniform(0.05, 0.15))
            logging.info(f"input_elements password : {self._password}\r")
           
            time.sleep(random.uniform(0.3, 0.8))  # 输入密码后等待

            # 点击登录按钮 — 先滚动到按钮位置确保可见
            try:
                # 找到可见的登录按钮（.el-button--primary 且 text=登录）
                all_primary_btns = driver.find_elements(By.CSS_SELECTOR, '.el-button--primary')
                login_btn = None
                for btn in all_primary_btns:
                    if btn.is_displayed() and '登录' in btn.text:
                        login_btn = btn
                        break
                if login_btn:
                    driver.execute_script("arguments[0].scrollIntoView({behavior: 'smooth', block: 'center'});", login_btn)
                    time.sleep(0.5)
                    driver.execute_script("arguments[0].click();", login_btn)
                    logging.info("Clicked login button.\r")
                else:
                    logging.warning("No visible login button found, trying fallback.")
                    login_btn = driver.find_element(By.CSS_SELECTOR, '.el-button--primary')
                    driver.execute_script("arguments[0].scrollIntoView({behavior: 'smooth', block: 'center'});", login_btn)
                    time.sleep(0.5)
                    driver.execute_script("arguments[0].click();", login_btn)
                    logging.info("Clicked login button (fallback).\r")
            except Exception as e:
                logging.warning(f"Failed to find/click login button: {e}")
            time.sleep(self.RETRY_WAIT_TIME_OFFSET_UNIT*2 + random.uniform(1, 2))
            logging.info("Click login button.\r")
            # sometimes ddddOCR may fail, so add retry logic)
            for retry_times in range(1, self.RETRY_TIMES_LIMIT + 1):
                # 等待滑块验证码容器出现（点击登录后才会加载）
                try:
                    WebDriverWait(driver, 15).until(
                        EC.presence_of_element_located((By.ID, "slideVerify")))
                    logging.info("CAPTCHA container (#slideVerify) appeared.\r")
                except Exception as e:
                    logging.warning(f"CAPTCHA not appeared after login click: {e}")
                    # 可能不需要验证码或已登录成功
                    if driver.current_url != LOGIN_URL:
                        logging.info("URL changed, may have logged in without CAPTCHA.\r")
                        break
                    continue

                # 尝试点击滑块验证码触发按钮（如果需要手动触发）
                try:
                    slide_btn = driver.find_element(By.CSS_SELECTOR, '.slide-verify-btn')
                    if slide_btn.is_displayed():
                        driver.execute_script("arguments[0].click();", slide_btn)
                        logging.info("Clicked slide-verify-btn.\r")
                        time.sleep(1)
                except:
                    pass  # CAPTCHA might already be active
                #get canvas image
                background_JS = 'return document.getElementById("slideVerify").childNodes[0].toDataURL("image/png");'
                # targe_JS = 'return document.getElementsByClassName("slide-verify-block")[0].toDataURL("image/png");'
                # get base64 image data
                im_info = driver.execute_script(background_JS) 
                background = im_info.split(',')[1]  
                background_image = base64_to_PLI(background)
                logging.info(f"Get electricity canvas image successfully.\r")
                distance = self.onnx.get_distance(background_image)
                # ONNX model detects on 416x416 space; scale to actual canvas width
                canvas_width = driver.execute_script(
                    'return document.getElementById("slideVerify").childNodes[0].width;'
                )
                scale = canvas_width / 416.0
                # 直接缩放到canvas尺寸，不再用复杂的sliding_scale
                scaled_distance = round(distance * scale)
                logging.info(f"CAPTCHA distance={distance}, canvas_width={canvas_width}, scale={scale:.3f}, scaled={scaled_distance}\r")

                time.sleep(random.uniform(0.5, 1.5))  # 滑动前随机等待
                self._sliding_track(driver, scaled_distance)
                time.sleep(self.RETRY_WAIT_TIME_OFFSET_UNIT + random.uniform(0.5, 1.5))
                
                # 调试：滑动后截图 - 全页面截图确保包含错误弹窗
                try:
                    debug_dir = "/config/debug/screenshots"
                    import os
                    os.makedirs(debug_dir, exist_ok=True)
                    timestamp = time.strftime("%Y%m%d_%H%M%S")
                    screenshot_path = f"{debug_dir}/after_slide_{timestamp}.png"
                    # 滚动到页面顶部确保弹窗可见
                    driver.execute_script("window.scrollTo(0, 0);")
                    time.sleep(0.5)
                    driver.save_screenshot(screenshot_path)
                    logging.info(f"Debug screenshot saved: {screenshot_path}\\r")
                except Exception as e:
                    logging.debug(f"Failed to save debug screenshot: {e}")
                
                if (driver.current_url == LOGIN_URL): # if login not success
                    try:
                        error = self._get_error_message(driver, "//div[@class='errmsg-tip']//span")
                        if error:
                            # 网络连接超时（RK001）,请重试！ 可能是登录次数过多导致
                            logging.info(f"Sliding CAPTCHA recognition failed [{error}] and loaded.\\r")
                        
                        # 调试：失败时截图 - 全页面截图包含错误提示
                        try:
                            debug_dir = "/config/debug/screenshots"
                            import os
                            os.makedirs(debug_dir, exist_ok=True)
                            timestamp = time.strftime("%Y%m%d_%H%M%S")
                            fail_screenshot = f"{debug_dir}/fail_{timestamp}.png"
                            # 滚动到顶部，等待错误弹窗渲染
                            driver.execute_script("window.scrollTo(0, 0);")
                            time.sleep(1)
                            driver.save_screenshot(fail_screenshot)
                            logging.info(f"Debug fail screenshot saved: {fail_screenshot}\\r")
                        except Exception as e:
                            logging.debug(f"Failed to save fail screenshot: {e}")
                        else:
                            logging.info(f"Sliding CAPTCHA recognition failed and reloaded.\\r")

                        self._click_button(driver, By.CSS_SELECTOR, ".el-button.el-button--primary")
                        time.sleep(self.RETRY_WAIT_TIME_OFFSET_UNIT*2)
                        continue
                    except:
                        logging.debug(
                            f"Login failed, maybe caused by invalid captcha, {self.RETRY_TIMES_LIMIT - retry_times} retry times left.")
                else:
                    return True
            logging.error(f"Login failed, maybe caused by Sliding CAPTCHA recognition failed")
        return self._fallback_login(driver)

    def _get_error_message(self, driver, path) -> Optional[str]:
        """获取错误信息，如果不存在则返回 None"""
        # 关闭隐式等待
        driver.implicitly_wait(0)
        try:
            element = driver.find_element(By.XPATH, path)
            return element.text
        except Exception:
            return None
        finally:
            driver.implicitly_wait(self.DRIVER_IMPLICITY_WAIT_TIME)  # 恢复隐式等待

    def _fallback_login(self, driver) -> bool:
        """使用 fallback 登录"""
        fallback = os.getenv("LOGIN_FALLBACK")
        if fallback == 'qrcode':
            return self._qr_login(driver)
        return False

    def _qr_login(self, driver) -> bool:
        logging.info("qrcode login start")
        # 切换验证码
        element = WebDriverWait(driver, self.DRIVER_IMPLICITY_WAIT_TIME).until(
            EC.presence_of_element_located((By.CLASS_NAME, 'qr_code')))
        driver.execute_script("arguments[0].click();", element)
        logging.info("switch to qrcode mode")

        time.sleep(self.RETRY_WAIT_TIME_OFFSET_UNIT)
        # 获取登录二维码
        qrElement = WebDriverWait(driver, self.DRIVER_IMPLICITY_WAIT_TIME).until(
            EC.visibility_of_element_located((By.XPATH, "//div[@class='sweepCodePic']//img")))
        logging.info("find imgLogin element")

        img_src = qrElement.get_attribute('src')

        if img_src.startswith('data:image'):
            base64_data = img_src.split(',')[1]
            img_screenshot = base64.b64decode(base64_data)
        else:
          logging.info('qrcode img src not base64')
          img_screenshot = qrElement.screenshot_as_png

        with open("/data/login_qr_code.png", "wb") as f:
            f.write(img_screenshot)
            logging.info("save qrcode to /data/login_qr_code.png")

        from notify import UrlLoginQrCodeNotify
        notifyFunc = UrlLoginQrCodeNotify()
        notifyFunc(img_screenshot)
        for i in range(1, self.QR_CODE_LOGIN_WAIT_COUNT + 1):
            logging.info(f'qrcode check login wait[{self.QR_CODE_LOGIN_WAIT_TIME_INTERVAL_UNIT}] count[{i}]')
            time.sleep(self.QR_CODE_LOGIN_WAIT_TIME_INTERVAL_UNIT)
            if (driver.current_url != LOGIN_URL):
                logging.info("qrcode Login success")
                return True
            else:
                error = self._get_error_message(driver, "//div[@class='sweepCodePic']//div[@class='erwBg']//p")
                if error is not None:
                    logging.error(f'qrcode login error[{error}]')
                    return False

        logging.warning("qrcode Login timeout")

        return False
        
    def fetch(self):

        """main logic here"""

        driver = self._get_webdriver()
        ErrorWatcher.instance().set_driver(driver)
        
        driver.maximize_window() 
        time.sleep(self.RETRY_WAIT_TIME_OFFSET_UNIT)
        logging.info("Webdriver initialized.")
        updator = SensorUpdator()
        
        try:
            if os.getenv("DEBUG_MODE", "false").lower() == "true":
                if self._login(driver,phone_code=True):
                    logging.info("login successed !")
                else:
                    logging.info("login unsuccessed !")
                    raise Exception("login unsuccessed")
            else:
                if self._login(driver):
                    logging.info("login successed !")
                else:
                    logging.info("login unsuccessed !")
                    raise Exception("login unsuccessed")
        except Exception as e:
            logging.error(
                f"Webdriver quit abnormly, reason: {e}. {self.RETRY_TIMES_LIMIT} retry times left.")
            driver.quit()
            return

        logging.info(f"Login successfully on {LOGIN_URL}")
        time.sleep(self.RETRY_WAIT_TIME_OFFSET_UNIT)
        logging.info(f"Try to get the userid list")
        user_id_list = self._get_user_ids(driver)
        logging.info(f"Here are a total of {len(user_id_list)} userids, which are {user_id_list} among which {self.IGNORE_USER_ID} will be ignored.")
        time.sleep(self.RETRY_WAIT_TIME_OFFSET_UNIT)


        for userid_index, user_id in enumerate(user_id_list):           
            try: 
                # switch to electricity charge balance page
                driver.get(BALANCE_URL) 
                time.sleep(self.RETRY_WAIT_TIME_OFFSET_UNIT)
                self._choose_current_userid(driver,userid_index)
                time.sleep(self.RETRY_WAIT_TIME_OFFSET_UNIT)
                current_userid = self._get_current_userid(driver)
                if current_userid in self.IGNORE_USER_ID:
                    logging.info(f"The user ID {current_userid} will be ignored in user_id_list")
                    continue
                else:
                    ### get data 
                    balance, last_daily_date, last_daily_usage, yearly_charge, yearly_usage, month_charge, month_usage  = self._get_all_data(driver, user_id, userid_index)
                    updator.update_one_userid(user_id, balance, last_daily_date, last_daily_usage, yearly_charge, yearly_usage, month_charge, month_usage)
        
                    time.sleep(self.RETRY_WAIT_TIME_OFFSET_UNIT)
            except Exception as e:
                if (userid_index != len(user_id_list)):
                    logging.info(f"The current user {user_id} data fetching failed {e}, the next user data will be fetched.")
                else:
                    logging.info(f"The user {user_id} data fetching failed, {e}")
                    logging.info("Webdriver quit after fetching data successfully.")
                continue

        driver.quit()


    def _get_current_userid(self, driver):
        current_userid = driver.find_element(By.XPATH, '//*[@id="app"]/div/div/article/div/div/div[2]/div/div/div[1]/div[2]/div/div/div/div[2]/div/div[1]/div/ul/div/li[1]/span[2]').text
        return current_userid
    
    def _choose_current_userid(self, driver, userid_index):
        elements = driver.find_elements(By.CLASS_NAME, "button_confirm")
        if elements:
            self._click_button(driver, By.XPATH, f'''//*[@id="app"]/div/div[2]/div/div/div/div[2]/div[2]/div/button''')
        time.sleep(self.RETRY_WAIT_TIME_OFFSET_UNIT)
        self._click_button(driver, By.CLASS_NAME, "el-input__suffix")
        time.sleep(self.RETRY_WAIT_TIME_OFFSET_UNIT)
        self._click_button(driver, By.XPATH, f"/html/body/div[2]/div[1]/div[1]/ul/li[{userid_index+1}]/span")
        

    def _get_all_data(self, driver, user_id, userid_index):
        balance = self._get_electric_balance(driver)
        if (balance is None):
            logging.error(f"Get electricity charge balance for {user_id} failed, Pass.")
        else:
            logging.info(
                f"Get electricity charge balance for {user_id} successfully, balance is {balance} CNY.")
        #time.sleep(self.RETRY_WAIT_TIME_OFFSET_UNIT)
        # swithc to electricity usage page
        driver.get(ELECTRIC_USAGE_URL)
        time.sleep(self.RETRY_WAIT_TIME_OFFSET_UNIT)
        self._choose_current_userid(driver, userid_index)
        time.sleep(self.RETRY_WAIT_TIME_OFFSET_UNIT)
        # get data for each user id
        yearly_usage, yearly_charge = self._get_yearly_data(driver)

        if yearly_usage is None:
            logging.error(f"Get year power usage for {user_id} failed, pass")
        else:
            logging.info(
                f"Get year power usage for {user_id} successfully, usage is {yearly_usage} kwh")
        if yearly_charge is None:
            logging.error(f"Get year power charge for {user_id} failed, pass")
        else:
            logging.info(
                f"Get year power charge for {user_id} successfully, yealrly charge is {yearly_charge} CNY")

        # 按月获取数据
        month, month_usage, month_charge = self._get_month_usage(driver)
        if month is None:
            logging.error(f"Get month power usage for {user_id} failed, pass")
        else:
            for m in range(len(month)):
                logging.info(f"Get month power charge for {user_id} successfully, {month[m]} usage is {month_usage[m]} KWh, charge is {month_charge[m]} CNY.")
        # get yesterday usage
        last_daily_date, last_daily_usage = self._get_yesterday_usage(driver)
        if last_daily_usage is None:
            logging.error(f"Get daily power consumption for {user_id} failed, pass")
        else:
            logging.info(
                f"Get daily power consumption for {user_id} successfully, , {last_daily_date} usage is {last_daily_usage} kwh.")
        if month is None:
            logging.error(f"Get month power usage for {user_id} failed, pass")

        # 新增储存用电量
        if self.db is not None:
            # 将数据存储到数据库
            logging.info(f"db is {self.db_type}, we will store the data to the database.")
            # 按天获取数据 7天/30天
            date, usages = self._get_daily_usage_data(driver)
            self._save_user_data(user_id, balance, last_daily_date, last_daily_usage, date, usages, month, month_usage, month_charge, yearly_charge, yearly_usage)
        else:
            logging.info("db is None, we will not store the data to the database.")

        
        if month_charge:
            month_charge = month_charge[-1]
        else:
            month_charge = None
        if month_usage:
            month_usage = month_usage[-1]
        else:
            month_usage = None

        return balance, last_daily_date, last_daily_usage, yearly_charge, yearly_usage, month_charge, month_usage

    def _get_user_ids(self, driver):
        try:
            # 刷新网页
            driver.refresh()
            time.sleep(self.RETRY_WAIT_TIME_OFFSET_UNIT*2)
            element = WebDriverWait(driver, self.DRIVER_IMPLICITY_WAIT_TIME).until(EC.presence_of_element_located((By.CLASS_NAME, 'el-dropdown')))
            # click roll down button for user id
            self._click_button(driver, By.XPATH, "//div[@class='el-dropdown']/span")
            logging.debug(f'''self._click_button(driver, By.XPATH, "//div[@class='el-dropdown']/span")''')
            time.sleep(self.RETRY_WAIT_TIME_OFFSET_UNIT)
            # wait for roll down menu displayed
            target = driver.find_element(By.CLASS_NAME, "el-dropdown-menu.el-popper").find_element(By.TAG_NAME, "li")
            logging.debug(f'''target = driver.find_element(By.CLASS_NAME, "el-dropdown-menu.el-popper").find_element(By.TAG_NAME, "li")''')
            time.sleep(self.RETRY_WAIT_TIME_OFFSET_UNIT)
            WebDriverWait(driver, self.DRIVER_IMPLICITY_WAIT_TIME).until(EC.visibility_of(target))
            time.sleep(self.RETRY_WAIT_TIME_OFFSET_UNIT)
            logging.debug(f'''WebDriverWait(driver, self.DRIVER_IMPLICITY_WAIT_TIME).until(EC.visibility_of(target))''')
            WebDriverWait(driver, self.DRIVER_IMPLICITY_WAIT_TIME).until(
                EC.text_to_be_present_in_element((By.XPATH, "//ul[@class='el-dropdown-menu el-popper']/li"), ":"))
            time.sleep(self.RETRY_WAIT_TIME_OFFSET_UNIT)

            # get user id one by one
            userid_elements = driver.find_element(By.CLASS_NAME, "el-dropdown-menu.el-popper").find_elements(By.TAG_NAME, "li")
            userid_list = []
            for element in userid_elements:
                userid_list.append(re.findall("[0-9]+", element.text)[-1])
            return userid_list
        except Exception as e:
            logging.error(
                f"Webdriver quit abnormly, reason: {e}. get user_id list failed.")
            driver.quit()

    def _get_electric_balance(self, driver):
        """
        获取电费余额 - 支持多种页面格式
        """
        try:
            # 方法1: 后缴费账户 - 查找"应交金额"标题
            try:
                title_text = driver.find_element(By.XPATH, "//p[contains(@class, 'balance_title') and contains(text(), '应交金额')]").text
                if "应交金额" in title_text:
                    balance_content = driver.find_element(By.XPATH, "//p[contains(@class, 'balance_title') and contains(text(), '账户余额')]")
                    balance_text = re.sub(r'[^\d.]', '', balance_content.text)
                    if balance_text:
                        logging.info(f"Method 1 (balance_title): Found balance {balance_text}")
                        return float(balance_text)
            except:
                pass

            # 方法2: 预缴费账户 - 查找 cff8 类元素
            try:
                balance_text = driver.find_element(By.CLASS_NAME, "cff8").text
                balance = balance_text.replace("元", "")
                if "欠费" in balance_text:
                    logging.info(f"Method 2 (cff8): Found debt balance -{balance}")
                    return -float(balance)
                else:
                    logging.info(f"Method 2 (cff8): Found balance {balance}")
                    return float(balance)
            except:
                pass

            # 方法3: 通用方法 - 从页面文本中用正则提取余额
            # 支持格式: "您的账户余额为：47.08元"、"账户余额：47.08元"、"余额：47.08元"
            page_text = driver.find_element(By.TAG_NAME, "body").text
            
            # 匹配 "您的账户余额为：xxx元"
            match = re.search(r'您的账户余额为[：:]*\s*([\d.]+)', page_text)
            if match:
                balance = match.group(1)
                logging.info(f"Method 3a (regex): Found balance {balance}")
                return float(balance)
            
            # 匹配 "账户余额：xxx元" 或 "账户余额为xxx元"
            match = re.search(r'账户余额[为：:]*\s*([\d.]+)', page_text)
            if match:
                balance = match.group(1)
                logging.info(f"Method 3b (regex): Found balance {balance}")
                return float(balance)
            
            # 匹配 "余额：xxx元"
            match = re.search(r'余额[：:]*\s*([\d.]+)', page_text)
            if match:
                balance = match.group(1)
                logging.info(f"Method 3c (regex): Found balance {balance}")
                return float(balance)
            
            # 匹配 "xxx元" (最后尝试)
            match = re.search(r'([\d.]+)元', page_text)
            if match:
                balance = match.group(1)
                logging.info(f"Method 3d (regex fallback): Found balance {balance}")
                return float(balance)
            
            logging.error("All methods failed to find balance")
            return None
            
        except Exception as e:
            logging.error(f"Failed to get balance: {e}")
            return None

    def _get_yearly_data(self, driver):

        try:
            if datetime.now().month == 1:
                self._click_button(driver, By.XPATH, '//*[@id="pane-first"]/div[1]/div/div[1]/div/div/input')
                time.sleep(self.RETRY_WAIT_TIME_OFFSET_UNIT)
                span_element = driver.find_element(By.XPATH, f"//span[text() = '{datetime.now().year - 1}']")
                span_element.click()
                time.sleep(self.RETRY_WAIT_TIME_OFFSET_UNIT)
            self._click_button(driver, By.XPATH, "//div[@class='el-tabs__nav is-top']/div[@id='tab-first']")
            time.sleep(self.RETRY_WAIT_TIME_OFFSET_UNIT)
            # wait for data displayed
            target = driver.find_element(By.CLASS_NAME, "total")
            WebDriverWait(driver, self.DRIVER_IMPLICITY_WAIT_TIME).until(EC.visibility_of(target))
        except Exception as e:
            logging.error(f"The yearly data get failed : {e}")
            return None, None

        # get data
        try:
            yearly_usage = driver.find_element(By.XPATH, "//ul[@class='total']/li[1]/span").text
        except Exception as e:
            logging.error(f"The yearly_usage data get failed : {e}")
            yearly_usage = None

        try:
            yearly_charge = driver.find_element(By.XPATH, "//ul[@class='total']/li[2]/span").text
        except Exception as e:
            logging.error(f"The yearly_charge data get failed : {e}")
            yearly_charge = None

        return yearly_usage, yearly_charge

    def _get_yesterday_usage(self, driver):
        """获取最近一次用电量"""
        try:
            # 点击日用电量
            self._click_button(driver, By.XPATH, "//div[@class='el-tabs__nav is-top']/div[@id='tab-second']")
            time.sleep(self.RETRY_WAIT_TIME_OFFSET_UNIT)
            # wait for data displayed
            usage_element = driver.find_element(By.XPATH,
                                                "//div[@class='el-tab-pane dayd']//div[@class='el-table__body-wrapper is-scrolling-none']/table/tbody/tr[1]/td[2]/div")
            WebDriverWait(driver, self.DRIVER_IMPLICITY_WAIT_TIME).until(EC.visibility_of(usage_element)) # 等待用电量出现

            # 增加是哪一天
            date_element = driver.find_element(By.XPATH,
                                                "//div[@class='el-tab-pane dayd']//div[@class='el-table__body-wrapper is-scrolling-none']/table/tbody/tr[1]/td[1]/div")
            last_daily_date = date_element.text # 获取最近一次用电量的日期
            return last_daily_date, float(usage_element.text)
        except Exception as e:
            logging.error(f"The yesterday data get failed : {e}")
            return None, None

    def _get_month_usage(self, driver):
        """获取每月用电量"""

        try:
            self._click_button(driver, By.XPATH, "//div[@class='el-tabs__nav is-top']/div[@id='tab-first']")
            time.sleep(self.RETRY_WAIT_TIME_OFFSET_UNIT)
            if datetime.now().month == 1:
                self._click_button(driver, By.XPATH, '//*[@id="pane-first"]/div[1]/div/div[1]/div/div/input')
                time.sleep(self.RETRY_WAIT_TIME_OFFSET_UNIT)
                span_element = driver.find_element(By.XPATH, f"//span[text() = '{datetime.now().year - 1}']")
                span_element.click()
                time.sleep(self.RETRY_WAIT_TIME_OFFSET_UNIT)
            # wait for month displayed
            target = driver.find_element(By.CLASS_NAME, "total")
            WebDriverWait(driver, self.DRIVER_IMPLICITY_WAIT_TIME).until(EC.visibility_of(target))
            month_element = driver.find_element(By.XPATH, "//*[@id='pane-first']/div[1]/div[2]/div[2]/div/div[3]/table/tbody").text
            month_element = month_element.split("\n")
            month_element = [x for x in month_element if x != "MAX"]
            if len(month_element) % 3 != 0:
                month_element = month_element[:-(len(month_element) % 3)]
            month_element = np.array(month_element).reshape(-1, 3)
            # 将每月的用电量保存为List
            month = []
            usage = []
            charge = []
            for i in range(len(month_element)):
                month.append(month_element[i][0])
                usage.append(month_element[i][1])
                charge.append(month_element[i][2])
            return month, usage, charge
        except Exception as e:
            logging.error(f"The month data get failed : {e}")
            return None,None,None

    # 增加获取每日用电量的函数
    def _get_daily_usage_data(self, driver):
        """储存指定天数的用电量"""
        retention_days = int(os.getenv("DATA_RETENTION_DAYS", 7))  # 默认值为7天
        self._click_button(driver, By.XPATH, "//div[@class='el-tabs__nav is-top']/div[@id='tab-second']")
        time.sleep(self.RETRY_WAIT_TIME_OFFSET_UNIT)

        # 7 天在第一个 label, 30 天 开通了智能缴费之后才会出现在第二个, (sb sgcc)
        if retention_days == 7:
            self._click_button(driver, By.XPATH, "//*[@id='pane-second']/div[1]/div/label[1]/span[1]")
        elif retention_days == 30:
            self._click_button(driver, By.XPATH, "//*[@id='pane-second']/div[1]/div/label[2]/span[1]")
        else:
            logging.error(f"Unsupported retention days value: {retention_days}")
            return

        time.sleep(self.RETRY_WAIT_TIME_OFFSET_UNIT)

        # 等待用电量的数据出现
        usage_element = driver.find_element(By.XPATH,
                                            "//div[@class='el-tab-pane dayd']//div[@class='el-table__body-wrapper is-scrolling-none']/table/tbody/tr[1]/td[2]/div")
        WebDriverWait(driver, self.DRIVER_IMPLICITY_WAIT_TIME).until(EC.visibility_of(usage_element))

        # 获取用电量的数据
        days_element = driver.find_elements(By.XPATH,
                                            "//*[@id='pane-second']/div[2]/div[2]/div[1]/div[3]/table/tbody/tr")  # 用电量值列表
        date = []
        usages = []
        # 将用电量保存为字典
        for i in days_element:
            day = i.find_element(By.XPATH, "td[1]/div").text
            usage = i.find_element(By.XPATH, "td[2]/div").text
            if usage != "":
                usages.append(usage)
                date.append(day)
            else:
                logging.info(f"The electricity consumption of {usage} get nothing")
        return date, usages

    def _save_user_data(self, user_id, balance, last_daily_date, last_daily_usage, date, usages, month, month_usage, month_charge, yearly_charge, yearly_usage):
        # 连接数据库集合
        if self.db.connect_user_db(user_id):
            # 写入当前户号
            dic = {'name': 'user', 'value': f"{user_id}"}
            self.insert_expand_data(dic)
            # 写入剩余金额
            dic = {'name': 'balance', 'value': f"{balance}"}
            self.insert_expand_data(dic)
            # 写入最近一次更新时间
            dic = {'name': f"daily_date", 'value': f"{last_daily_date}"}
            self.insert_expand_data(dic)
            # 写入最近一次更新时间用电量
            dic = {'name': f"daily_usage", 'value': f"{last_daily_usage}"}
            self.insert_expand_data(dic)
            
            # 写入年用电量
            dic = {'name': 'yearly_usage', 'value': f"{yearly_usage}"}
            self.insert_expand_data(dic)
            # 写入年用电电费
            dic = {'name': 'yearly_charge', 'value': f"{yearly_charge} "}
            self.insert_expand_data(dic)

            if date: 
                for index in range(len(date)):
                    dic = {'date': date[index], 'usage': float(usages[index])}
                    # 插入到数据库
                    try:
                        self.db.insert_data(dic)
                        logging.info(f"The electricity consumption of {usages[index]}KWh on {date[index]} has been successfully deposited into the database")
                    except Exception as e:
                        logging.debug(f"The electricity consumption of {date[index]} failed to save to the database, which may already exist: {str(e)}")
            if month: 
                for index in range(len(month)):
                    try:
                        dic = {'name': f"{month[index]}usage", 'value': f"{month_usage[index]}"}
                        self.db.insert_expand_data(dic)
                        dic = {'name': f"{month[index]}charge", 'value': f"{month_charge[index]}"}
                        self.db.insert_expand_data(dic)
                    except Exception as e:
                        logging.debug(f"The electricity consumption of {month[index]} failed to save to the database, which may already exist: {str(e)}")
            if month_charge:
                month_charge = month_charge[-1]
            else:
                month_charge = None
                
            if month_usage:
                month_usage = month_usage[-1]
            else:
                month_usage = None
            # 写入本月电量
            dic = {'name': f"month_usage", 'value': f"{month_usage}"}
            self.insert_expand_data(dic)
            # 写入本月电费
            dic = {'name': f"month_charge", 'value': f"{month_charge}"}
            self.insert_expand_data(dic)
            # dic = {'date': month[index], 'usage': float(month_usage[index]), 'charge': float(month_charge[index])}
            self.db.close_connect()
        else:
            logging.info("The database creation failed and the data was not written correctly.")
            return

if __name__ == "__main__":
    with open("bg.jpg", "rb") as f:
        test1 = f.read()
        print(type(test1))
        print(test1)

