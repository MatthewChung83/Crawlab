# Crawlab Docker Image
# Python 3.11 + Playwright + 所有爬蟲依賴

FROM python:3.11-slim

LABEL maintainer="Crawlab Team"
LABEL description="Crawlab - Web Crawler Platform with n8n Integration"

# 設定工作目錄
WORKDIR /app

# 設定環境變數
ENV PYTHONUNBUFFERED=1
ENV PYTHONIOENCODING=utf-8
ENV TZ=Asia/Taipei
ENV DEBIAN_FRONTEND=noninteractive

# 安裝系統依賴
RUN apt-get update && apt-get install -y --no-install-recommends \
    # SQL Server ODBC Driver 依賴
    unixodbc-dev \
    freetds-dev \
    freetds-bin \
    tdsodbc \
    # SMB 客戶端
    smbclient \
    # SSH 客戶端
    openssh-client \
    # 中文字型
    fonts-noto-cjk \
    fonts-wqy-zenhei \
    # 網路工具
    curl \
    wget \
    netcat-openbsd \
    # 其他
    git \
    tzdata \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# 設定時區
RUN ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone

# 複製 requirements.txt 並安裝 Python 依賴
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# 安裝 Playwright 及瀏覽器
RUN pip install --no-cache-dir playwright && \
    playwright install chromium && \
    playwright install-deps chromium

# 複製專案檔案
COPY . .

# 建立必要目錄
RUN mkdir -p /app/logs /app/output /app/temp

# 設定檔案權限
RUN chmod +x run_module.sh 2>/dev/null || true

# 健康檢查
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/api/v1/health || exit 1

# 暴露 API 端口
EXPOSE 8000

# 預設執行 API Gateway
CMD ["uvicorn", "api_gateway:app", "--host", "0.0.0.0", "--port", "8000"]
