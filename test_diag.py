#!/usr/bin/env python3
"""Quick diagnostic: check what the slide-verify elements actually look like."""
import sys, os, time
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'scripts'))

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from const import LOGIN_URL

PHONE = "18637036878"
PASSWORD = "li19890630"

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
    time.sleep(1)

    # ===== Dump all element info =====
    diag = driver.execute_script("""
    var result = {};
    
    // Canvas info
    var canvas = document.getElementById("slideVerify").childNodes[0];
    result.canvas_width = canvas.width;
    result.canvas_height = canvas.height;
    result.canvas_style = canvas.style.cssText;
    
    // slide-verify-block
    var blocks = document.getElementsByClassName("slide-verify-block");
    result.block_count = blocks.length;
    if (blocks.length > 0) {
        var b = blocks[0];
        result.block_tag = b.tagName;
        result.block_width_attr = b.width;
        result.block_height_attr = b.height;
        result.block_offsetWidth = b.offsetWidth;
        result.block_offsetHeight = b.offsetHeight;
        var rect = b.getBoundingClientRect();
        result.block_rect = {width: rect.width, height: rect.height, x: rect.x, y: rect.y};
        result.block_style = b.style.cssText;
        result.block_class = b.className;
    }
    
    // slide-verify-slider-mask-item (slider handle)
    var sliders = document.getElementsByClassName("slide-verify-slider-mask-item");
    result.slider_count = sliders.length;
    if (sliders.length > 0) {
        var s = sliders[0];
        result.slider_tag = s.tagName;
        result.slider_offsetWidth = s.offsetWidth;
        result.slider_offsetHeight = s.offsetHeight;
        var srect = s.getBoundingClientRect();
        result.slider_rect = {width: srect.width, height: srect.height, x: srect.x, y: srect.y};
    }
    
    // slide-verify-slider-mask
    var masks = document.getElementsByClassName("slide-verify-slider-mask");
    result.mask_count = masks.length;
    if (masks.length > 0) {
        var m = masks[0];
        result.mask_offsetWidth = m.offsetWidth;
        var mrect = m.getBoundingClientRect();
        result.mask_rect = {width: mrect.width, height: mrect.height, x: mrect.x, y: mrect.y};
    }
    
    return result;
    """)
    
    import json
    print(json.dumps(diag, indent=2))
    
finally:
    driver.quit()
