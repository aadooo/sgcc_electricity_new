"""
优化后的登录策略
1. 优先账号密码登录 + 验证码识别
2. 验证码识别失败自动切换到二维码登录
3. 二维码通过hermes推送到微信
"""
import logging
import time
import os
import base64
import random
from selenium.webdriver.common.by import By
from selenium.webdriver.support.wait import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC


class OptimizedLoginStrategy:
    """优化的登录策略"""

    def __init__(self, data_fetcher):
        self.fetcher = data_fetcher
        self.max_captcha_retry = 3  # 验证码最多重试3次

    def login(self, driver):
        """
        智能登录策略
        1. 尝试账号密码 + 验证码识别（最多3次）
        2. 失败后自动切换二维码登录
        """
        # 检查是否强制使用二维码
        force_qrcode = os.getenv("FORCE_QRCODE_LOGIN", "false").lower() == "true"

        if force_qrcode:
            logging.info("强制使用二维码登录")
            return self._qrcode_login(driver)

        # 策略1：尝试账号密码登录
        if self.fetcher._password and len(self.fetcher._password) > 0:
            logging.info("尝试账号密码登录...")

            for attempt in range(1, self.max_captcha_retry + 1):
                logging.info(f"验证码识别尝试 {attempt}/{self.max_captcha_retry}")

                try:
                    success = self._password_login_with_captcha(driver)
                    if success:
                        logging.info("✓ 账号密码登录成功")
                        return True
                    else:
                        logging.warning(f"✗ 验证码识别失败 (尝试 {attempt}/{self.max_captcha_retry})")

                        # 如果是最后一次尝试，切换到二维码
                        if attempt >= self.max_captcha_retry:
                            logging.info("验证码识别失败次数过多，切换到二维码登录")
                            break

                        # 刷新页面重试
                        driver.refresh()
                        time.sleep(3)

                except Exception as e:
                    logging.error(f"账号密码登录异常: {e}")
                    if attempt >= self.max_captcha_retry:
                        break

        # 策略2：降级到二维码登录
        logging.info("切换到二维码登录...")
        return self._qrcode_login(driver)

    def _password_login_with_captcha(self, driver):
        """账号密码登录 + 验证码识别"""
        try:
            # 1. 切换到密码登录模式
            if not self._switch_to_password_mode(driver):
                return False

            # 2. 输入账号密码
            if not self._input_credentials(driver):
                return False

            # 3. 点击登录按钮
            if not self._click_login_button(driver):
                return False

            # 4. 处理验证码
            captcha_result = self._handle_captcha_smart(driver)

            if captcha_result == 'success':
                # 验证是否登录成功
                time.sleep(3)
                from const import LOGIN_URL
                if driver.current_url != LOGIN_URL:
                    return True
                else:
                    logging.warning("验证码通过但登录失败")
                    return False
            elif captcha_result == 'no_captcha':
                # 没有验证码，直接检查登录状态
                time.sleep(2)
                from const import LOGIN_URL
                return driver.current_url != LOGIN_URL
            else:
                return False

        except Exception as e:
            logging.error(f"密码登录过程异常: {e}")
            return False

    def _switch_to_password_mode(self, driver):
        """切换到密码登录模式"""
        try:
            # 等待页面加载
            WebDriverWait(driver, 15).until(
                EC.visibility_of_element_located((By.CLASS_NAME, "user")))

            # 关闭可能的弹窗
            try:
                modal_buttons = driver.find_elements(By.CSS_SELECTOR, '.modal-container button')
                for btn in modal_buttons:
                    if '同意' in btn.text:
                        driver.execute_script("arguments[0].click();", btn)
                        time.sleep(1)
                        break
            except:
                pass

            # 切换到密码登录（通过Vue方法）
            switched = driver.execute_script("""
                var allEls = document.querySelectorAll('*');
                for (var i = 0; i < allEls.length; i++) {
                    if (allEls[i].__vue__ && allEls[i].__vue__.$options.methods &&
                        allEls[i].__vue__.$options.methods.userLoginClick) {
                        allEls[i].__vue__.userLoginClick();
                        return true;
                    }
                }
                return false;
            """)

            if not switched:
                # 备用方案：直接点击切换按钮
                try:
                    switch_el = driver.find_element(By.CSS_SELECTOR,
                        '.ewm-login .login_ewm .switch .switchs.sweepCode')
                    driver.execute_script("arguments[0].click();", switch_el)
                except:
                    logging.error("无法切换到密码登录模式")
                    return False

            # 等待登录表单可见
            WebDriverWait(driver, 10).until(
                EC.visibility_of_element_located((By.CSS_SELECTOR, '.account-login')))

            time.sleep(1)
            return True

        except Exception as e:
            logging.error(f"切换到密码模式失败: {e}")
            return False

    def _input_credentials(self, driver):
        """输入账号密码"""
        try:
            # 勾选同意协议
            try:
                checkbox = driver.find_element(By.CSS_SELECTOR,
                    '.password_form .checked-box.un-checked')
                driver.execute_script("arguments[0].click();", checkbox)
            except:
                pass

            # 获取输入框
            pwd_form = driver.find_element(By.CSS_SELECTOR, '.password_form')
            input_elements = pwd_form.find_elements(By.CSS_SELECTOR, '.el-input__inner')

            if len(input_elements) < 2:
                logging.error("找不到账号密码输入框")
                return False

            # 输入账号（模拟人类输入）
            for char in self.fetcher._username:
                input_elements[0].send_keys(char)
                time.sleep(random.uniform(0.05, 0.15))

            time.sleep(random.uniform(0.5, 1.0))

            # 输入密码
            for char in self.fetcher._password:
                input_elements[1].send_keys(char)
                time.sleep(random.uniform(0.05, 0.15))

            time.sleep(random.uniform(0.3, 0.8))

            logging.info("账号密码输入完成")
            return True

        except Exception as e:
            logging.error(f"输入账号密码失败: {e}")
            return False

    def _click_login_button(self, driver):
        """点击登录按钮"""
        try:
            # 找到可见的登录按钮
            all_primary_btns = driver.find_elements(By.CSS_SELECTOR, '.el-button--primary')
            login_btn = None

            for btn in all_primary_btns:
                if btn.is_displayed() and '登录' in btn.text:
                    login_btn = btn
                    break

            if not login_btn:
                logging.error("找不到登录按钮")
                return False

            # 滚动到按钮并点击
            driver.execute_script(
                "arguments[0].scrollIntoView({behavior: 'smooth', block: 'center'});",
                login_btn)
            time.sleep(0.5)
            driver.execute_script("arguments[0].click();", login_btn)

            logging.info("点击登录按钮")
            time.sleep(2)
            return True

        except Exception as e:
            logging.error(f"点击登录按钮失败: {e}")
            return False

    def _handle_captcha_smart(self, driver):
        """
        智能验证码处理
        返回: 'success', 'failed', 'no_captcha'
        """
        try:
            # 等待验证码容器出现（或超时）
            try:
                WebDriverWait(driver, 10).until(
                    EC.presence_of_element_located((By.ID, "slideVerify")))
                logging.info("检测到滑动验证码")
            except:
                logging.info("未检测到验证码，可能直接登录成功")
                return 'no_captcha'

            # 尝试识别滑动验证码
            try:
                # 获取验证码图片
                background_JS = 'return document.getElementById("slideVerify").childNodes[0].toDataURL("image/png");'
                im_info = driver.execute_script(background_JS)
                background = im_info.split(',')[1]

                from data_fetcher import base64_to_PLI
                background_image = base64_to_PLI(background)

                # 使用ONNX模型识别距离
                distance = self.fetcher.onnx.get_distance(background_image)

                # 缩放到实际canvas尺寸
                canvas_width = driver.execute_script(
                    'return document.getElementById("slideVerify").childNodes[0].width;')
                scale = canvas_width / 416.0
                scaled_distance = round(distance * scale)

                logging.info(f"验证码距离: {distance}, 缩放后: {scaled_distance}")

                # 滑动
                time.sleep(random.uniform(0.5, 1.0))
                self.fetcher._sliding_track(driver, scaled_distance)
                time.sleep(3)

                # 检查是否成功
                from const import LOGIN_URL
                if driver.current_url != LOGIN_URL:
                    logging.info("✓ 验证码识别成功")
                    return 'success'
                else:
                    # 检查是否有错误提示
                    try:
                        error_el = driver.find_element(By.CSS_SELECTOR, '.el-message--error')
                        if error_el.is_displayed():
                            logging.warning(f"✗ 验证码错误: {error_el.text}")
                            return 'failed'
                    except:
                        pass

                    logging.warning("✗ 验证码识别失败")
                    return 'failed'

            except Exception as e:
                logging.error(f"验证码识别异常: {e}")
                return 'failed'

        except Exception as e:
            logging.error(f"验证码处理异常: {e}")
            return 'failed'

    def _qrcode_login(self, driver):
        """二维码登录（通过hermes推送到微信）"""
        try:
            logging.info("=" * 60)
            logging.info("开始二维码登录流程")
            logging.info("=" * 60)

            # 1. 切换到二维码登录模式
            try:
                qr_switch = WebDriverWait(driver, 10).until(
                    EC.presence_of_element_located((By.CLASS_NAME, 'qr_code')))
                driver.execute_script("arguments[0].click();", qr_switch)
                logging.info("✓ 切换到二维码模式")
                time.sleep(2)
            except Exception as e:
                logging.error(f"✗ 切换到二维码模式失败: {e}")
                return False

            # 2. 获取二维码图片
            try:
                qr_img = WebDriverWait(driver, 10).until(
                    EC.visibility_of_element_located((By.XPATH, "//div[@class='sweepCodePic']//img")))

                img_src = qr_img.get_attribute('src')

                if img_src.startswith('data:image'):
                    base64_data = img_src.split(',')[1]
                    img_bytes = base64.b64decode(base64_data)
                else:
                    img_bytes = qr_img.screenshot_as_png

                # 保存二维码
                qr_path = "/data/login_qr_code.png"
                with open(qr_path, "wb") as f:
                    f.write(img_bytes)
                logging.info(f"✓ 二维码已保存: {qr_path}")

            except Exception as e:
                logging.error(f"✗ 获取二维码失败: {e}")
                return False

            # 3. 推送二维码到微信（通过hermes）
            try:
                import urllib.request
                url = os.getenv("PUSH_QRCODE_URL", "http://192.168.1.95:9100/qrcode")

                logging.info(f"推送二维码到: {url}")
                req = urllib.request.Request(
                    url,
                    data=img_bytes,
                    headers={"Content-Type": "image/png"},
                    method='POST'
                )

                with urllib.request.urlopen(req, timeout=10) as resp:
                    logging.info(f"✓ Hermes推送成功: HTTP {resp.status}")
                    logging.info("请在微信中扫描二维码登录")

            except Exception as e:
                logging.warning(f"✗ Hermes推送失败: {e}")
                logging.info("尝试备用推送方式...")

                # 备用推送方式
                try:
                    from notify import UrlLoginQrCodeNotify
                    notifyFunc = UrlLoginQrCodeNotify()
                    notifyFunc(img_bytes)
                    logging.info("✓ 备用推送成功")
                except Exception as e2:
                    logging.error(f"✗ 备用推送也失败: {e2}")

            # 4. 等待用户扫码
            wait_count = self.fetcher.QR_CODE_LOGIN_WAIT_COUNT
            wait_interval = self.fetcher.QR_CODE_LOGIN_WAIT_TIME_INTERVAL_UNIT

            logging.info(f"等待扫码登录 (最多 {wait_count * wait_interval} 秒)...")

            from const import LOGIN_URL
            for i in range(1, wait_count + 1):
                time.sleep(wait_interval)

                # 检查是否登录成功
                if driver.current_url != LOGIN_URL:
                    logging.info("=" * 60)
                    logging.info("✓ 二维码登录成功！")
                    logging.info("=" * 60)
                    return True

                # 检查二维码是否过期
                try:
                    error_el = driver.find_element(By.XPATH,
                        "//div[@class='sweepCodePic']//div[@class='erwBg']//p")
                    if error_el.is_displayed():
                        error_text = error_el.text
                        logging.error(f"✗ 二维码错误: {error_text}")
                        return False
                except:
                    pass

                if i % 5 == 0:
                    logging.info(f"等待中... ({i}/{wait_count})")

            logging.warning("=" * 60)
            logging.warning("✗ 二维码登录超时")
            logging.warning("=" * 60)
            return False

        except Exception as e:
            logging.error(f"二维码登录异常: {e}")
            return False


# 使用示例：
"""
在 data_fetcher.py 的 fetch() 方法中替换登录逻辑：

from optimized_login_strategy import OptimizedLoginStrategy

def fetch(self):
    driver = self._get_webdriver()
    driver.maximize_window()

    try:
        # 使用优化的登录策略
        login_strategy = OptimizedLoginStrategy(self)

        if login_strategy.login(driver):
            logging.info("登录成功")
        else:
            logging.error("登录失败")
            raise Exception("Login failed")

        # 继续后续逻辑...

    except Exception as e:
        logging.error(f"异常: {e}")
        driver.quit()
        return
"""
