#!/usr/bin/env python3
"""Full integration test: login + captcha + balance extraction on real 95598.cn"""
import sys, os, time, random, re, base64, logging
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'scripts'))

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver import ActionChains
from PIL import Image
from io import BytesIO
from const import LOGIN_URL, BALANCE_URL

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
log = logging.getLogger("test")

PHONE = "18637036878"
PASSWORD = "li19890630"

def init_driver():
    opts = Options()
    opts.add_argument("--headless=new")
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-gpu")
    opts.add_argument("--disable-dev-shm-usage")
    opts.add_argument("--start-maximized")
    opts.add_argument("--disable-blink-features=AutomationControlled")
    opts.add_experimental_option("excludeSwitches", ["enable-automation"])
    opts.add_experimental_option("useAutomationExtension", False)
    opts.add_argument("user-agent=Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36")
    driver = webdriver.Chrome(options=opts)
    driver.implicitly_wait(60)
    driver.set_window_size(1920, 1080)
    return driver

def click_js(driver, by, key):
    el = driver.find_element(by, key)
    driver.execute_script("arguments[0].click();", el)
    return el

def do_login(driver):
    """Login flow from data_fetcher.py _login method"""
    log.info(f"Navigating to {LOGIN_URL}")
    driver.get(LOGIN_URL)
    WebDriverWait(driver, 180).until(EC.visibility_of_element_located((By.CLASS_NAME, "user")))
    log.info("Page loaded, waiting for content...")
    time.sleep(20)

    # Wait for loading mask to disappear
    driver.implicitly_wait(0)
    try:
        WebDriverWait(driver, 10).until(
            EC.invisibility_of_element_located((By.CLASS_NAME, 'el-loading-mask')))
    finally:
        driver.implicitly_wait(60)

    # Switch to username-password login tab
    click_js(driver, By.CLASS_NAME, 'user')
    log.info("Clicked user tab")
    click_js(driver, By.XPATH, '//*[@id="login_box"]/div[1]/div[1]/div[2]/span')
    log.info("Switched to password login")
    time.sleep(15)

    # Click agree checkbox
    click_js(driver, By.XPATH, '//*[@id="login_box"]/div[2]/div[1]/form/div[1]/div[3]/div/span[2]')
    log.info("Clicked agree")
    time.sleep(15)

    # Agree checkbox (unchecked)
    try:
        cb = driver.find_element(By.CLASS_NAME, "checked-box.un-checked")
        driver.execute_script("arguments[0].click();", cb)
        time.sleep(0.5)
        log.info("Clicked agree checkbox")
    except Exception as e:
        log.info(f"Agree checkbox: {e}")

    # Fill credentials
    inputs = driver.find_elements(By.CLASS_NAME, "el-input__inner")
    inputs[0].send_keys(PHONE)
    inputs[1].send_keys(PASSWORD)
    log.info(f"Filled phone={PHONE}")

    # Click login button
    click_js(driver, By.CLASS_NAME, "el-button.el-button--primary")
    log.info("Clicked login button")

    # Wait for sliding captcha
    time.sleep(15 + random.uniform(0.5, 1.5))

    try:
        WebDriverWait(driver, 15).until(
            EC.presence_of_element_located((By.ID, "slideVerify")))
        log.info("Slide verify canvas loaded")
        time.sleep(1)
    except Exception as e:
        log.warning(f"Slide verify not found: {e}")
        if driver.current_url != LOGIN_URL:
            log.info("Already logged in!")
            return True

    # ONNX model for captcha
    from onnx import ONNX
    onnx = ONNX("./scripts/captcha.onnx")

    for retry in range(1, 6):
        log.info(f"=== Captcha attempt {retry}/5 ===")
        try:
            # Get canvas image
            bg_js = 'return document.getElementById("slideVerify").childNodes[0].toDataURL("image/png");'
            im_info = driver.execute_script(bg_js)
            bg_data = im_info.split(',')[1]
            bg_bytes = base64.b64decode(bg_data)
            bg_image = Image.open(BytesIO(bg_bytes))
            log.info(f"Canvas image: {bg_image.size}")

            # Canvas dimensions
            canvas_w = driver.execute_script('return document.getElementById("slideVerify").childNodes[0].width;')
            canvas_h = driver.execute_script('return document.getElementById("slideVerify").childNodes[0].height;')
            log.info(f"Canvas size: {canvas_w}x{canvas_h}")

            # Slider handle width (slide-verify-slider-mask-item is the DIV handle, not the block canvas)
            try:
                block_w = driver.execute_script(
                    'return document.getElementsByClassName("slide-verify-slider-mask-item")[0].getBoundingClientRect().width;'
                )
            except:
                block_w = 40
            log.info(f"Slider handle width: {block_w}")

            # Letterbox resize to 416x416
            model_size = 416
            orig_w, orig_h = bg_image.size
            scale = min(model_size / orig_w, model_size / orig_h)
            new_w = int(orig_w * scale)
            new_h = int(orig_h * scale)
            resized = bg_image.resize((new_w, new_h), Image.LANCZOS)
            padded = Image.new('RGB', (model_size, model_size), (114, 114, 114))
            pad_x = (model_size - new_w) // 2
            pad_y = (model_size - new_h) // 2
            padded.paste(resized, (pad_x, pad_y))

            # ONNX inference
            distance = onnx.get_distance(padded)
            if distance <= 0:
                log.warning("ONNX failed, using fallback distance")
                distance = random.randint(150, 280)

            # Coordinate restore
            img_distance = (distance - pad_x) / scale
            max_sliding = canvas_w - block_w
            offset = random.uniform(-5, 5)
            scaled_distance = round(img_distance + offset)
            scaled_distance = max(50, min(scaled_distance, max_sliding))

            log.info(f"CAPTCHA: raw={distance}, scale={scale:.3f}, pad=({pad_x},{pad_y}), "
                     f"img_dist={img_distance:.1f}, canvas={canvas_w}x{canvas_h}, "
                     f"block_w={block_w}, final={scaled_distance}")

            # Sliding action (4-phase human-like)
            slider = driver.find_element(By.CLASS_NAME, "slide-verify-slider-mask-item")
            ActionChains(driver).click_and_hold(slider).perform()
            time.sleep(random.uniform(0.05, 0.1))

            moved = 0
            accel_end = scaled_distance * 0.35
            cruise_end = scaled_distance * 0.75
            decel_end = scaled_distance * 0.95

            while moved < scaled_distance:
                remaining = scaled_distance - moved
                if moved < accel_end:
                    step = random.randint(10, 20)
                    delay = random.uniform(0.008, 0.025)
                elif moved < cruise_end:
                    step = random.randint(6, 12)
                    delay = random.uniform(0.015, 0.035)
                elif moved < decel_end:
                    step = random.randint(3, 7)
                    delay = random.uniform(0.025, 0.05)
                else:
                    step = random.randint(1, 3)
                    delay = random.uniform(0.04, 0.08)
                step = min(step, remaining)
                y_jitter = random.uniform(-1.5, 1.5)
                ActionChains(driver).move_by_offset(xoffset=step, yoffset=y_jitter).perform()
                moved += step
                time.sleep(delay)
                if random.random() < 0.1:
                    time.sleep(random.uniform(0.05, 0.15))

            time.sleep(random.uniform(0.03, 0.08))
            rebound = random.randint(1, 4)
            ActionChains(driver).move_by_offset(xoffset=-rebound, yoffset=random.uniform(-0.5, 0.5)).perform()
            time.sleep(random.uniform(0.05, 0.12))
            ActionChains(driver).release().perform()
            time.sleep(random.uniform(0.1, 0.2))

            log.info(f"Slid {scaled_distance}px, waiting for result...")
            time.sleep(15)

            # Check login status
            if driver.current_url != LOGIN_URL:
                log.info(f"✓ Login successful! URL: {driver.current_url}")
                return True

            # Check error
            try:
                err = driver.find_element(By.XPATH, "//div[@class='errmsg-tip']//span").text
                log.warning(f"Captcha failed: {err}")
            except:
                log.warning("Captcha failed, no error message found")

            # Refresh and retry
            try:
                refresh = driver.find_element(By.CLASS_NAME, "slide-verify-refresh-btn")
                driver.execute_script("arguments[0].click();", refresh)
                time.sleep(0.5)
            except:
                pass

            click_js(driver, By.CLASS_NAME, "el-button.el-button--primary")
            time.sleep(20 + random.uniform(0.5, 1.5))

        except Exception as e:
            log.error(f"Attempt {retry} error: {e}")
            time.sleep(random.uniform(1.0, 3.0))
            continue

    log.error("All captcha attempts failed")
    return False


def get_balance(driver):
    """Navigate to balance page and extract balance"""
    log.info(f"Navigating to balance page: {BALANCE_URL}")
    driver.get(BALANCE_URL)
    time.sleep(15)

    # Check for popup dialogs and dismiss
    popups = [
        "//button[contains(text(), '确定')]",
        "//button[contains(text(), '我知道了')]",
        "//span[contains(text(), '关闭')]",
        "//div[@class='el-dialog__headerbtn']",
    ]
    for xpath in popups:
        try:
            btn = driver.find_element(By.XPATH, xpath)
            if btn.is_displayed():
                driver.execute_script("arguments[0].click();", btn)
                time.sleep(0.5)
                log.info(f"Dismissed popup: {xpath}")
        except:
            pass

    # Save debug screenshot
    debug_dir = "/tmp/sgcc_debug"
    os.makedirs(debug_dir, exist_ok=True)
    ss_path = os.path.join(debug_dir, f"balance_{time.strftime('%Y%m%d_%H%M%S')}.png")
    driver.save_screenshot(ss_path)
    log.info(f"Screenshot saved: {ss_path}")

    # Save page source
    html_path = os.path.join(debug_dir, f"balance_{time.strftime('%Y%m%d_%H%M%S')}.html")
    with open(html_path, "w", encoding="utf-8") as f:
        f.write(driver.page_source)
    log.info(f"Page source saved: {html_path}")

    # Try balance extraction methods (from _get_electric_balance)
    # Method 0: Prepaid selectors
    prepaid_selectors = [
        ("//div[contains(@class,'balance')]//span[contains(@class,'money')]", None),
        ("//div[contains(@class,'account-balance')]//span", None),
        ("//span[contains(text(), '当前可用余额')]", "parent"),
        ("//span[contains(text(), '账户余额')]", "parent"),
        ("//span[contains(text(), '电费余额')]", "parent"),
        ("//p[contains(text(), '余额')]", "sibling"),
        ("//div[contains(text(), '余额')]", "sibling"),
        ("//h3[contains(text(), '余额')]", "sibling"),
    ]

    for xpath, mode in prepaid_selectors:
        try:
            elem = driver.find_element(By.XPATH, xpath)
            if mode == "parent":
                parent = elem
                for _ in range(5):
                    parent = parent.find_element(By.XPATH, "..")
                    text = parent.text
                    match = re.search(r'(\d+\.?\d*)\s*元', text)
                    if match:
                        amount = float(match.group(1))
                        if 0 < amount < 100000:
                            log.info(f"[Method0] Found via parent: {amount} 元 (text: {text[:80]})")
                            return amount, ss_path, html_path
            elif mode == "sibling":
                parent = elem
                for _ in range(3):
                    parent = parent.find_element(By.XPATH, "..")
                    for child in parent.find_elements(By.XPATH, ".//*[contains(text(), '元')]"):
                        match = re.search(r'(\d+\.?\d*)\s*元', child.text)
                        if match:
                            amount = float(match.group(1))
                            if 0 < amount < 100000:
                                log.info(f"[Method0] Found via sibling: {amount} 元")
                                return amount, ss_path, html_path
        except:
            continue

    # Method 1: Text patterns
    balance_patterns = [
        ("您的账户余额为：", "cff8"),
        ("当前可用余额", None),
        ("电费余额", None),
        ("待交电费", None),
        ("上月应交电费", None),
        ("应交电费", None),
        ("余额", "cff8"),
    ]

    for pattern, css_class in balance_patterns:
        try:
            container = driver.find_element(By.XPATH, f"//*[contains(text(), '{pattern}')]")
            if css_class:
                try:
                    val = container.find_element(By.CLASS_NAME, css_class).text.strip()
                    bal = val.replace("元", "").replace("￥", "").strip()
                    if re.match(r'^[\d.]+$', bal):
                        log.info(f"[Method1] Pattern '{pattern}' + class '{css_class}': {bal}")
                        return float(bal), ss_path, html_path
                except:
                    pass

            parent = container
            for _ in range(5):
                try:
                    parent = parent.find_element(By.XPATH, "..")
                    for elem in parent.find_elements(By.XPATH, ".//*[contains(text(), '元')]"):
                        match = re.search(r'(\d+\.?\d*)元', elem.text)
                        if match:
                            log.info(f"[Method1] Parent search: {match.group(1)}")
                            return float(match.group(1)), ss_path, html_path
                except:
                    break
        except:
            continue

    # Method 2: All "元" elements
    try:
        for elem in driver.find_elements(By.XPATH, "//*[contains(text(), '元')]"):
            text = elem.text.strip()
            match = re.search(r'(\d+\.?\d*)元', text)
            if match:
                amount = float(match.group(1))
                if 0 < amount < 100000:
                    log.info(f"[Method2] '元' search: {amount} (from: {text})")
                    return amount, ss_path, html_path
    except Exception as e:
        log.debug(f"Method2 failed: {e}")

    # Method 3: XPath selectors
    xpaths = [
        "//b[@class='cff8']",
        "//span[contains(@class, 'money')]",
        "//span[contains(@class, 'balance')]",
        "//div[contains(@class, 'balance')]//span",
        "//p[contains(., '余额')]//b",
        "//p[contains(., '电费')]//span",
        "//div[contains(@class, 'info')]//span[contains(@class, 'cff8')]",
    ]

    for xpath in xpaths:
        try:
            for elem in driver.find_elements(By.XPATH, xpath):
                text = elem.text.strip()
                match = re.search(r'(\d+\.?\d*)', text)
                if match:
                    amount = float(match.group(1))
                    if 0 < amount < 100000:
                        log.info(f"[Method3] xpath '{xpath}': {amount}")
                        return amount, ss_path, html_path
        except:
            continue

    log.warning("ALL balance extraction methods FAILED")
    return None, ss_path, html_path


def main():
    driver = None
    try:
        driver = init_driver()
        log.info("Driver initialized")

        # Step 1: Login
        if not do_login(driver):
            log.error("Login failed, stopping")
            return

        # Step 2: Get balance
        result = get_balance(driver)
        balance, ss_path, html_path = result

        if balance is not None:
            log.info(f"★★★ BALANCE: {balance} 元 ★★★")
        else:
            log.error("Failed to extract balance!")
            log.info(f"Debug files: {ss_path}, {html_path}")

            # Dump some page text for analysis
            try:
                body = driver.find_element(By.TAG_NAME, "body").text
                log.info(f"Page body text:\n{body[:1000]}")
            except:
                pass

    except Exception as e:
        log.error(f"Test failed: {e}")
        import traceback
        traceback.print_exc()
    finally:
        if driver:
            driver.quit()
            log.info("Driver closed")


if __name__ == "__main__":
    main()
