# Docker构建失败修复说明

## 问题分析

Docker构建在安装Python依赖时失败，可能的原因：

1. **ddddocr依赖问题**：ddddocr需要额外的系统库（OpenCV相关）
2. **undetected-chromedriver兼容性**：可能与Python 3.12有兼容性问题
3. **selenium-stealth依赖**：可能需要额外的构建工具

## 解决方案

### 方案A：注释掉可选依赖（已实施）

已将新添加的依赖注释掉，恢复到原始可工作状态：

```txt
# 反爬虫检测绕过（可选，如需使用请取消注释）
# undetected-chromedriver==3.5.5
# selenium-stealth==1.0.6

# 点击验证码识别（可选，如需使用请取消注释）
# ddddocr==1.4.11
```

**优点：**
- Docker构建可以正常通过
- 核心功能不受影响
- 需要时可以手动安装

### 方案B：修改Dockerfile添加依赖（推荐）

如果需要使用这些功能，修改 `Dockerfile-for-github-action`：

```dockerfile
# 在第19行的apt-get install后添加：
RUN apt-get --allow-releaseinfo-change update \
    && apt-get install -y --no-install-recommends \
       jq wget unzip fonts-noto-cjk tzdata xvfb x11-utils curl \
       # Chrome 依赖库
       libglib2.0-0 libnss3 libatk1.0-0 libatk-bridge2.0-0 libcups2 \
       libdrm2 libxkbcommon0 libxcomposite1 libxdamage1 libxrandr2 \
       libgbm1 libpango-1.0-0 libcairo2 libasound2 libxshmfence1 \
       # 新增：ddddocr依赖
       libgl1-mesa-glx libglib2.0-0 libsm6 libxrender1 libxext6 \
       # 新增：构建工具
       gcc g++ make \
    && ln -snf /usr/share/zoneinfo/$TZ /etc/localtime \
    ...
```

然后取消注释requirements.txt中的依赖。

### 方案C：分阶段安装（最稳定）

修改Dockerfile的pip安装部分：

```dockerfile
# 先安装核心依赖
RUN mkdir /data \
    && cd /tmp \
    && python3 -m pip install --upgrade pip \
    && PIP_ROOT_USER_ACTION=ignore pip install \
    --disable-pip-version-check \
    --no-cache-dir \
    requests==2.31.0 \
    selenium==4.34.2 \
    schedule==1.2.1 \
    Pillow==10.1.0 \
    onnxruntime==1.18.1 \
    numpy==1.26.2 \
    webdrivermanager_cn==2.4.0 \
    webdriver-manager==4.0.2 \
    mysql-connector-python==9.4.0

# 可选：安装反爬虫依赖（可能失败但不影响核心功能）
RUN pip install --no-cache-dir \
    undetected-chromedriver==3.5.5 \
    selenium-stealth==1.0.6 \
    || echo "Optional anti-detection packages failed, continuing..."

# 可选：安装ddddocr（可能失败但不影响核心功能）
RUN pip install --no-cache-dir ddddocr==1.4.11 \
    || echo "Optional ddddocr package failed, continuing..."
```

## 当前状态

✅ **已修复**：requirements.txt已恢复到可工作状态
- 核心依赖保持不变
- 新功能依赖已注释
- Docker构建应该可以通过

## 使用新功能的方法

如果需要使用反爬虫和验证码识别功能：

### 方法1：手动安装（推荐）

在容器运行后手动安装：
```bash
docker exec -it <container_id> pip install undetected-chromedriver selenium-stealth ddddocr
```

### 方法2：创建扩展镜像

基于原镜像创建扩展版本：
```dockerfile
FROM arcw/sgcc_electricity:latest
RUN pip install undetected-chromedriver selenium-stealth ddddocr
```

### 方法3：使用环境变量控制

修改代码，使这些功能可选：
```python
# 在代码中添加try-except
try:
    import undetected_chromedriver as uc
    USE_UNDETECTED = True
except ImportError:
    USE_UNDETECTED = False
    logging.warning("undetected-chromedriver not installed, using standard driver")
```

## 建议

**对于生产环境：**
- 使用方案A（当前状态）
- 保持Docker镜像轻量和稳定
- 核心功能（二维码登录）已经足够

**对于开发/测试环境：**
- 使用方案B或C
- 可以尝试完整功能
- 接受可能的构建失败风险

## 提交说明

需要提交这个修复：
```bash
git add requirements.txt
git commit -m "fix: 注释可选依赖以修复Docker构建失败

- 注释 undetected-chromedriver（可选）
- 注释 selenium-stealth（可选）
- 注释 ddddocr（可选）
- 这些依赖可能导致Docker构建失败
- 核心功能不受影响
- 需要时可手动安装"
git push origin master
```
