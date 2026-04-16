#!/usr/bin/env python3
"""Capture captcha screenshot for manual analysis."""
import sys, os, time
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'scripts'))

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from const import LOGIN_URL
import base64

PHONE = "18637036878"
PASSWORD = "li19890630"

opts = Options()
opts.add_argument("--headless=new")
opts.add_argument("--no-sandbox")
opts.add_argument("--disable-gpu")
opts.add_argument("--disable-dev-shm-usage")
opts.add_argument("--start-maximized")
opts.add_argument("--window-size=1920,1080")
opts.add_argument("--disable-blink-features=AutomationControlled")
opts.add_experimental_option("excludeSwitches", ["enable-automation"])
opts.add_experimental_option("useAutomationExtension", False)
opts.add_argument("user-agent=Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36")

driver = webdriver.Chrome(options=opts)
driver.implicitly_wait(60)
driver.set_window_size(1920, 1080)

OUT_DIR = "/tmp/sgcc_debug"
os.makedirs(OUT_DIR, exist_ok=True)

def click_js(driver, by, key):
    el = driver.find_element(by, key)
    driver.execute_script("arguments[0].click();", el)

try:
    driver.get(LOGIN_URL)
    WebDriverWait(driver, 180).until(EC.visibility_of_element_located((By.CLASS_NAME, "user")))
    time.sleep(20)

    click_js(driver, By.CLASS_NAME, 'user')
    click_js(driver, By.XPATH, '//*[@id="login_box"]/div[1]/div[1]/div[2]/span')
    time.sleep(15)
    click_js(driver, By.XPATH, '//*[@id="login_box"]/div[2]/div[1]/form/div[1]/div[3]/div/span[2]')
    time.sleep(15)

    try:
        cb = driver.find_element(By.CLASS_NAME, "checked-box.un-checked")
        driver.execute_script("arguments[0].click();", cb)
        time.sleep(0.5)
    except:
        pass

    inputs = driver.find_elements(By.CLASS_NAME, "el-input__inner")
    inputs[0].send_keys(PHONE)
    inputs[1].send_keys(PASSWORD)
    click_js(driver, By.CLASS_NAME, "el-button.el-button--primary")
    time.sleep(15)

    WebDriverWait(driver, 15).until(EC.presence_of_element_located((By.ID, "slideVerify")))
    time.sleep(2)

    # Save full page screenshot
    ss_path = os.path.join(OUT_DIR, "captcha_page.png")
    driver.save_screenshot(ss_path)
    print(f"SCREENSHOT:{ss_path}")

    # Save canvas image separately
    canvas_b64 = driver.execute_script(
        'return document.getElementById("slideVerify").childNodes[0].toDataURL("image/png");'
    )
    canvas_data = canvas_b64.split(',')[1]
    canvas_path = os.path.join(OUT_DIR, "captcha_canvas.png")
    with open(canvas_path, "wb") as f:
        f.write(base64.b64decode(canvas_data))
    print(f"CANVAS:{canvas_path}")

    # Save puzzle block image
    try:
        block_b64 = driver.execute_script(
            'return document.getElementsByClassName("slide-verify-block")[0].toDataURL("image/png");'
        )
        block_data = block_b64.split(',')[1]
        block_path = os.path.join(OUT_DIR, "captcha_block.png")
        with open(block_path, "wb") as f:
            f.write(base64.b64decode(block_data))
        print(f"BLOCK:{block_path}")
    except Exception as e:
        print(f"BLOCK_FAIL:{e}")

finally:
    driver.quit()
