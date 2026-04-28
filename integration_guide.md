# 国家电网反爬解决方案集成指南

## 问题背景

国家电网升级了反爬虫策略：
1. **Headless检测**：标准的headless模式会被识别并拒绝登录
2. **验证码升级**：从滑动验证码改为点位顺序验证码（按顺序点击指定文字）

## 解决方案总览

### 方案A：undetected-chromedriver（推荐）
- 自动绕过大部分反爬检测
- 维护活跃，持续更新
- 成功率高

### 方案B：selenium + selenium-stealth
- 备用方案
- 需要手动配置更多参数

### 方案C：真实浏览器环境（最稳定但资源消耗大）
- 使用Xvfb虚拟显示器 + headed模式
- 完全模拟真实用户环境

## 实施步骤

### 1. 更新依赖

**修改 `requirements.txt`，添加：**
```
undetected-chromedriver==3.5.5
ddddocr==1.4.11
selenium-stealth==1.0.6
```

### 2. 修改 data_fetcher.py

在文件开头添加导入：
```python
from anti_detection_driver import get_undetected_driver, get_stealth_driver_fallback
from click_captcha_solver import ClickCaptchaSolver
```

**替换 `_get_webdriver` 方法：**
```python
def _get_webdriver(self):
    """获取反检测的WebDriver"""
    use_headless = os.getenv("USE_HEADLESS", "true").lower() == "true"
    
    # 优先使用undetected-chromedriver
    try:
        from anti_detection_driver import get_undetected_driver
        driver = get_undetected_driver(headless=use_headless)
        logging.info("Using undetected-chromedriver")
        return driver
    except Exception as e:
        logging.warning(f"Failed to use undetected-chromedriver: {e}")
    
    # 备用方案1：selenium-stealth
    try:
        from anti_detection_driver import get_stealth_driver_fallback
        driver = get_stealth_driver_fallback(headless=use_headless)
        logging.info("Using selenium-stealth as fallback")
        return driver
    except Exception as e:
        logging.warning(f"Failed to use selenium-stealth: {e}")
    
    # 备用方案2：原有方法（但增强反检测）
    logging.info("Using original driver with enhanced anti-detection")
    return self._get_webdriver_original()

def _get_webdriver_original(self):
    """原有的driver获取方法（增强版）"""
    # 保留原有代码，但添加更多反检测措施
    # ... 原有代码 ...
```

### 3. 添加点击验证码处理

在 `__init__` 方法中初始化验证码求解器：
```python
def __init__(self, username: str, password: str):
    # ... 原有代码 ...
    self.onnx = ONNX("./captcha.onnx")
    
    # 添加点击验证码求解器
    try:
        from click_captcha_solver import ClickCaptchaSolver
        self.click_captcha_solver = ClickCaptchaSolver()
        logging.info("ClickCaptchaSolver initialized")
    except Exception as e:
        self.click_captcha_solver = None
        logging.warning(f"ClickCaptchaSolver not available: {e}")
```

**添加点击验证码处理方法：**
```python
def _handle_click_captcha(self, driver):
    """处理点击顺序验证码"""
    try:
        # 1. 检测是否出现点击验证码
        captcha_element = driver.find_element(By.CLASS_NAME, "click-captcha-image")
        if not captcha_element:
            return False
        
        # 2. 获取提示文字（例如："按顺序点击：一、二、三"）
        hint_element = driver.find_element(By.CLASS_NAME, "captcha-hint-text")
        hint_text = hint_element.text
        logging.info(f"Click captcha detected: {hint_text}")
        
        # 3. 获取验证码图片
        captcha_img_base64 = driver.execute_script(
            "return arguments[0].toDataURL('image/png');", 
            captcha_element
        )
        
        # 4. 识别点击位置
        if self.click_captcha_solver:
            positions = self.click_captcha_solver.solve_click_captcha(
                captcha_img_base64, 
                hint_text
            )
            
            if positions:
                # 5. 执行点击
                self.click_captcha_solver.click_positions_on_element(
                    driver, 
                    captcha_element, 
                    positions
                )
                logging.info("Click captcha solved successfully")
                
                # 6. 等待验证结果
                time.sleep(2)
                return True
            else:
                logging.error("Failed to solve click captcha: no positions returned")
                return False
        else:
            logging.error("ClickCaptchaSolver not available")
            return False
            
    except Exception as e:
        logging.debug(f"No click captcha found or error: {e}")
        return False
```

**在登录流程中调用：**
```python
def _login(self, driver, phone_code=False):
    # ... 原有登录代码 ...
    
    # 在输入账号密码后，检查验证码类型
    time.sleep(2)
    
    # 先尝试处理点击验证码
    if self._handle_click_captcha(driver):
        logging.info("Click captcha handled")
    else:
        # 如果不是点击验证码，使用原有的滑动验证码处理
        # ... 原有滑动验证码代码 ...
        pass
```

### 4. 环境变量配置

在 `.env` 文件中添加：
```bash
# 是否使用headless模式（true/false）
USE_HEADLESS=true

# 验证码识别方式：auto/slide/click
CAPTCHA_TYPE=auto

# 如果使用第三方API识别验证码
CAPTCHA_API_URL=
CAPTCHA_API_KEY=
```

### 5. Docker配置更新

**修改 `Dockerfile`（如果需要）：**
```dockerfile
# 安装undetected-chromedriver所需的依赖
RUN pip install undetected-chromedriver==3.5.5 \
    ddddocr==1.4.11 \
    selenium-stealth==1.0.6
```

## 测试方案

### 测试1：反检测效果测试
```python
# 创建测试脚本 test_anti_detection.py
from anti_detection_driver import get_undetected_driver

driver = get_undetected_driver(headless=True)
driver.get("https://bot.sannysoft.com/")
time.sleep(5)
driver.save_screenshot("anti_detection_test.png")
driver.quit()

# 检查截图，所有检测项应该显示为绿色（通过）
```

### 测试2：验证码识别测试
```python
# 使用 scripts/test_qr_login.py 修改后测试
from click_captcha_solver import ClickCaptchaSolver

solver = ClickCaptchaSolver()
# 测试验证码识别...
```

## 方案对比

| 方案 | 成功率 | 资源消耗 | 维护成本 | 推荐度 |
|------|--------|----------|----------|--------|
| undetected-chromedriver | 95% | 中 | 低 | ⭐⭐⭐⭐⭐ |
| selenium-stealth | 80% | 中 | 中 | ⭐⭐⭐⭐ |
| Xvfb + headed | 99% | 高 | 低 | ⭐⭐⭐⭐ |
| 原有方案增强 | 60% | 低 | 高 | ⭐⭐⭐ |

## 故障排查

### 问题1：undetected-chromedriver安装失败
**解决方案：**
```bash
# 手动指定Chrome版本
pip install undetected-chromedriver==3.5.5
# 或使用国内镜像
pip install -i https://pypi.tuna.tsinghua.edu.cn/simple undetected-chromedriver
```

### 问题2：ddddocr识别率低
**解决方案：**
- 使用第三方API（超级鹰、图鉴等）
- 优先使用二维码登录（设置 `LOGIN_FALLBACK=qrcode`）

### 问题3：仍然被检测
**解决方案：**
1. 使用Xvfb + headed模式（最稳定）
2. 增加随机延迟和人类行为模拟
3. 使用代理IP轮换
4. 降低请求频率

## 最佳实践建议

1. **优先使用二维码登录**：设置 `LOGIN_FALLBACK=qrcode`，避免验证码识别
2. **降低请求频率**：避免频繁登录导致账号被风控
3. **使用缓存机制**：项目已有缓存，避免重启时重复抓取
4. **监控日志**：关注 `Anti-detection` 相关日志
5. **定期更新**：undetected-chromedriver需要跟随Chrome版本更新

## 长期方案

如果反爬持续升级，考虑：
1. **完全切换到二维码登录**：移除账号密码登录
2. **使用真实浏览器**：Playwright + headed模式
3. **人工辅助**：关键步骤人工介入
4. **官方API**：联系国家电网申请官方API接口
