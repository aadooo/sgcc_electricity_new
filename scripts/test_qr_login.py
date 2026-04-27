#!/usr/bin/env python3
"""强制触发二维码登录，绕过密码登录流程"""
import os
import sys
import time
import logging
import base64

# Setup logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)-8s] %(message)s")
logger = logging.getLogger(__name__)

# Add scripts dir to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

LOGIN_URL = "https://95598.cn/osgweb/login"

def get_driver():
    options = Options()
    options.add_argument("--headless")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1920,1080")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option("useAutomationExtension", False)
    
    driver = webdriver.Chrome(options=options)
    driver.set_page_load_timeout(30)
    driver.implicitly_wait(10)
    
    # Anti-detection
    driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined});")
    
    return driver

def qr_login(driver):
    """强制走二维码登录"""
    logger.info("Opening login page...")
    driver.get(LOGIN_URL)
    time.sleep(5)
    
    logger.info("Looking for QR code element...")
    try:
        element = WebDriverWait(driver, 20).until(
            EC.presence_of_element_located((By.CLASS_NAME, 'qr_code')))
        driver.execute_script("arguments[0].click();", element)
        logger.info("Switched to QR code mode")
    except Exception as e:
        logger.error(f"Failed to find/click QR code element: {e}")
        # Try Vue method
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
            logger.info("Switched via Vue method")
            time.sleep(2)
    
    time.sleep(3)
    
    # Find QR code image
    try:
        qr_element = driver.find_element(By.CLASS_NAME, 'qr_code')
        img = qr_element.find_element(By.TAG_NAME, 'img')
        img_src = img.get_attribute('src')
        logger.info(f"QR code img src: {img_src[:50]}...")
        
        if img_src and img_src.startswith('data:image'):
            base64_data = img_src.split(',')[1]
            img_data = base64.b64decode(base64_data)
        else:
            img_data = img.screenshot_as_png
            logger.info("Using screenshot for QR code")
        
        output_path = "/tmp/test_login_qr.png"
        with open(output_path, "wb") as f:
            f.write(img_data)
        logger.info(f"QR code saved to {output_path}")
        
        # Push to Hermes bridge
        try:
            import urllib.request
            url = os.getenv("PUSH_QRCODE_URL", "http://192.168.1.95:9100/qrcode")
            req = urllib.request.Request(url, data=img_data, headers={"Content-Type": "image/png"}, method='POST')
            with urllib.request.urlopen(req, timeout=10) as resp:
                logger.info(f"Hermes QR push response: {resp.status}")
        except Exception as push_err:
            logger.error(f"Push failed: {push_err}")
        
        return True
        
    except Exception as e:
        logger.error(f"Failed to get QR code: {e}")
        driver.save_screenshot("/tmp/qr_error.png")
        logger.info("Screenshot saved to /tmp/qr_error.png")
        return False

if __name__ == "__main__":
    driver = None
    try:
        driver = get_driver()
        success = qr_login(driver)
        if success:
            logger.info("QR code login triggered successfully!")
        else:
            logger.error("QR code login failed")
    except Exception as e:
        logger.error(f"Error: {e}")
        if driver:
            driver.save_screenshot("/tmp/error_screenshot.png")
    finally:
        if driver:
            driver.quit()