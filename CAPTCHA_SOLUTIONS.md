# 验证码识别方案完整对比

## 问题：ddddocr识别率太低

ddddocr是开源免费方案，但存在以下问题：
- ✗ 识别率低（30-50%）
- ✗ 对复杂验证码效果差
- ✗ 需要大量样本训练
- ✗ 维护成本高

## 推荐方案对比

### 方案A：第三方打码平台（强烈推荐）

| 平台 | 识别率 | 价格 | 速度 | 推荐度 |
|------|--------|------|------|--------|
| **超级鹰** | 95%+ | ¥0.01/次 | 3-5秒 | ⭐⭐⭐⭐⭐ |
| **图鉴** | 93%+ | ¥0.008/次 | 3-6秒 | ⭐⭐⭐⭐ |
| **YesCaptcha** | 90%+ | $0.002/次 | 5-8秒 | ⭐⭐⭐⭐ |

**优点：**
- ✓ 识别率高（95%+）
- ✓ 稳定可靠
- ✓ 无需维护
- ✓ 支持多种验证码类型

**缺点：**
- ✗ 需要付费（但很便宜）
- ✗ 依赖网络

**成本分析：**
```
每天登录2次 × 每次1个验证码 × ¥0.01 = ¥0.02/天
一年成本：¥0.02 × 365 = ¥7.3/年
```

### 方案B：优先使用二维码登录（最推荐）

**优点：**
- ✓ 完全避免验证码
- ✓ 成功率99%+
- ✓ 免费
- ✓ 用户体验好

**实施方法：**
```bash
# .env配置
LOGIN_FALLBACK=qrcode
PUSH_QRCODE_URL=http://your-server/qrcode
```

### 方案C：训练自己的模型

**优点：**
- ✓ 免费
- ✓ 可定制

**缺点：**
- ✗ 需要大量样本（1000+）
- ✗ 需要GPU训练
- ✗ 维护成本高
- ✗ 验证码更新后需重新训练

**不推荐，除非：**
- 有大量验证码样本
- 有GPU资源
- 有机器学习经验

## 快速集成指南

### 1. 使用超级鹰（推荐）

**步骤1：注册账号**
- 访问：http://www.chaojiying.com/
- 注册并充值（最低10元）

**步骤2：配置环境变量**
```bash
# .env文件
CAPTCHA_SOLVER_PLATFORM=chaojiying
CHAOJIYING_USERNAME=your_username
CHAOJIYING_PASSWORD=your_password
CHAOJIYING_SOFT_ID=123456
```

**步骤3：使用**
```python
from click_captcha_solver import ClickCaptchaSolver

# 自动使用API识别
solver = ClickCaptchaSolver(solver_type='auto')
positions = solver.solve_click_captcha(image_base64, target_text)
```

### 2. 使用图鉴

**步骤1：注册**
- 访问：http://www.ttshitu.com/
- 注册并充值

**步骤2：配置**
```bash
# .env文件
CAPTCHA_SOLVER_PLATFORM=ttshitu
TTSHITU_USERNAME=your_username
TTSHITU_PASSWORD=your_password
```

### 3. 多方案自动降级

```python
# 优先API，失败则降级到ddddocr
solver = ClickCaptchaSolver(solver_type='auto')

# 仅使用API
solver = ClickCaptchaSolver(solver_type='api')

# 仅使用ddddocr（免费但识别率低）
solver = ClickCaptchaSolver(solver_type='ddddocr')
```

## 完整使用示例

```python
import os
from click_captcha_solver import ClickCaptchaSolver
from human_behavior_simulator import HumanBehaviorSimulator

# 1. 初始化求解器（自动选择最佳方案）
solver = ClickCaptchaSolver(solver_type='auto')

# 2. 获取验证码图片
captcha_element = driver.find_element(By.CLASS_NAME, "captcha-image")
image_base64 = driver.execute_script(
    "return arguments[0].toDataURL('image/png');",
    captcha_element
)

# 3. 获取提示文字
hint_text = driver.find_element(By.CLASS_NAME, "captcha-hint").text
# 例如："按顺序点击：一、二、三"

# 4. 识别验证码
positions = solver.solve_click_captcha(image_base64, hint_text)

if positions:
    # 5. 使用人类行为模拟点击
    HumanBehaviorSimulator.click_positions_human_like(
        driver, 
        captcha_element, 
        positions
    )
    print("✓ 验证码识别并点击成功")
else:
    print("✗ 验证码识别失败")
```

## 成本效益分析

### 场景1：个人使用（每天2次登录）

| 方案 | 年成本 | 识别率 | 维护成本 | 总评 |
|------|--------|--------|----------|------|
| 超级鹰 | ¥7.3 | 95% | 无 | ⭐⭐⭐⭐⭐ |
| ddddocr | ¥0 | 30% | 高 | ⭐⭐ |
| 二维码登录 | ¥0 | 99% | 低 | ⭐⭐⭐⭐⭐ |

**推荐：二维码登录 > 超级鹰 > ddddocr**

### 场景2：多用户部署（100用户）

| 方案 | 年成本 | 总评 |
|------|--------|------|
| 超级鹰 | ¥730 | ⭐⭐⭐⭐ |
| 自训练模型 | ¥0 + 开发成本 | ⭐⭐⭐ |
| 二维码登录 | ¥0 | ⭐⭐⭐⭐⭐ |

**推荐：二维码登录 > 超级鹰**

## 各平台详细对比

### 超级鹰 (Chaojiying)

**优点：**
- 老牌平台，稳定可靠
- 支持多种验证码类型
- 价格便宜（¥0.01/次）
- 有Python SDK

**缺点：**
- 界面较老
- 文档不够详细

**验证码类型代码：**
- 9004：点击文字（按顺序）
- 9005：点击图标（按顺序）
- 9101：滑动验证码

**注册链接：** http://www.chaojiying.com/

### 图鉴 (TTShiTu)

**优点：**
- 价格最便宜（¥0.008/次）
- API简单易用
- 识别速度快

**缺点：**
- 识别率略低于超级鹰
- 客服响应慢

**注册链接：** http://www.ttshitu.com/

### YesCaptcha

**优点：**
- 国际化平台
- 支持多种支付方式
- API文档完善

**缺点：**
- 价格较贵（$0.002/次）
- 需要美元支付

**注册链接：** https://yescaptcha.com/

## 故障排查

### 问题1：API识别失败

**可能原因：**
1. 账户余额不足
2. 用户名/密码错误
3. 网络连接问题
4. 验证码类型不匹配

**解决方案：**
```python
# 检查配置
import os
print(f"Platform: {os.getenv('CAPTCHA_SOLVER_PLATFORM')}")
print(f"Username: {os.getenv('CHAOJIYING_USERNAME')}")

# 测试API连接
from captcha_solver_api import CaptchaSolverAPI
solver = CaptchaSolverAPI(platform='chaojiying')
# 查看日志输出
```

### 问题2：识别率仍然低

**可能原因：**
1. 验证码类型选择错误
2. 图片质量差
3. 提示文字解析错误

**解决方案：**
```python
# 1. 保存验证码图片检查质量
with open('captcha_debug.png', 'wb') as f:
    f.write(base64.b64decode(image_base64.split(',')[1]))

# 2. 尝试不同的验证码类型
positions = solver.solve_click_captcha(image_base64, captcha_type='9005')

# 3. 检查提示文字
print(f"Hint text: {hint_text}")
```

### 问题3：成本太高

**解决方案：**
1. **优先使用二维码登录**（免费）
2. 降低登录频率（使用缓存）
3. 只在必要时才识别验证码
4. 使用更便宜的平台（图鉴）

## 最佳实践

### 1. 多方案组合

```python
# 优先级：二维码 > API > ddddocr
def smart_login(driver):
    # 1. 尝试二维码登录
    if try_qrcode_login(driver):
        return True
    
    # 2. 尝试API识别验证码
    solver = ClickCaptchaSolver(solver_type='api')
    if solve_captcha(driver, solver):
        return True
    
    # 3. 降级到ddddocr
    solver = ClickCaptchaSolver(solver_type='ddddocr')
    if solve_captcha(driver, solver):
        return True
    
    return False
```

### 2. 缓存机制

```python
# 避免频繁登录
# 项目已实现缓存，重启时优先从缓存恢复
# 参考 scripts/main.py 的 republish 机制
```

### 3. 监控识别率

```python
# 记录识别成功率
success_count = 0
total_count = 0

def solve_with_monitoring(solver, image, text):
    global success_count, total_count
    total_count += 1
    
    positions = solver.solve_click_captcha(image, text)
    if positions:
        success_count += 1
    
    rate = success_count / total_count * 100
    logging.info(f"识别成功率: {rate:.1f}% ({success_count}/{total_count})")
    
    return positions
```

## 总结

### 推荐方案（按优先级）

1. **二维码登录**（免费，99%成功率）
   - 设置 `LOGIN_FALLBACK=qrcode`
   - 配置二维码推送服务

2. **超级鹰API**（¥7.3/年，95%识别率）
   - 适合个人和小规模部署
   - 性价比最高

3. **图鉴API**（¥5.8/年，93%识别率）
   - 价格最便宜
   - 适合预算有限的场景

4. **ddddocr**（免费，30%识别率）
   - 仅作为最后的降级方案
   - 不推荐单独使用

### 不推荐

- ✗ 自己训练模型（成本高，维护难）
- ✗ 纯ddddocr方案（识别率太低）

### 最终建议

**对于本项目（国家电网电费采集）：**

```bash
# .env配置
# 优先使用二维码登录
LOGIN_FALLBACK=qrcode
PUSH_QRCODE_URL=http://your-server/qrcode

# 备用方案：超级鹰API
CAPTCHA_SOLVER_PLATFORM=chaojiying
CHAOJIYING_USERNAME=your_username
CHAOJIYING_PASSWORD=your_password
```

这样配置后：
- 正常情况：使用二维码登录（免费）
- 二维码失败：自动使用超级鹰识别验证码
- 成功率：99%+
- 年成本：< ¥10
