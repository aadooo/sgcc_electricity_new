#!/usr/bin/env python3
"""Test Chrome driver initialization and SGCC page access."""
import sys, os, time
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'scripts'))

from selenium import webdriver
from selenium.webdriver.chrome.options import Options

chrome_options = Options()
chrome_options.add_argument("--headless=new")
chrome_options.add_argument("--no-sandbox")
chrome_options.add_argument("--disable-gpu")
chrome_options.add_argument("--disable-dev-shm-usage")
chrome_options.add_argument("--disable-blink-features=AutomationControlled")
chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
chrome_options.add_experimental_option("useAutomationExtension", False)
chrome_options.add_argument("user-agent=Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36")

try:
    driver = webdriver.Chrome(options=chrome_options)
    print(f"✓ Chrome driver initialized")
    print(f"  Browser: {driver.capabilities.get('browserVersion', '?')}")
    cd_ver = driver.capabilities.get('chrome', {}).get('chromedriverVersion', '?')
    print(f"  Chromedriver: {cd_ver}")
    
    # Navigate to SGCC login
    driver.get("https://95598.cn/osgweb/login")
    time.sleep(5)
    print(f"  Page title: {driver.title}")
    print(f"  URL: {driver.current_url}")
    
    # Check if page loaded
    try:
        from selenium.webdriver.common.by import By
        from selenium.webdriver.support.ui import WebDriverWait
        from selenium.webdriver.support import expected_conditions as EC
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.TAG_NAME, "body"))
        )
        body_text = driver.find_element(By.TAG_NAME, "body").text[:200]
        print(f"  Body text (first 200 chars): {body_text}")
    except Exception as e:
        print(f"  Could not read body: {e}")
    
    driver.quit()
    print("✓ Clean exit")
except Exception as e:
    print(f"✗ FAILED: {type(e).__name__}: {e}")
    import traceback
    traceback.print_exc()
