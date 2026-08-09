FROM python:3.11-slim

# Thư viện build + tiện ích lấy khóa GPG của Microsoft
RUN apt-get update && apt-get install -y --no-install-recommends \
      gcc g++ curl gnupg apt-transport-https ca-certificates unixodbc-dev \
    && rm -rf /var/lib/apt/lists/*

# Driver ODBC THẬT cho SQL Server (kết nối HIS).
# `unixodbc-dev` chỉ là thư viện phát triển — thiếu gói này pyodbc sẽ báo
# "Can't open lib 'ODBC Driver 18 for SQL Server' : file not found".
RUN curl -fsSL https://packages.microsoft.com/keys/microsoft.asc \
      | gpg --dearmor -o /usr/share/keyrings/microsoft-prod.gpg \
    && echo "deb [arch=amd64,arm64 signed-by=/usr/share/keyrings/microsoft-prod.gpg] \
https://packages.microsoft.com/debian/12/prod bookworm main" \
      > /etc/apt/sources.list.d/mssql-release.list \
    && apt-get update \
    && ACCEPT_EULA=Y apt-get install -y --no-install-recommends msodbcsql18 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .

# Không chạy bằng root: hạn chế thiệt hại nếu một thư viện bị khai thác.
RUN useradd --create-home --uid 10001 appuser \
    && mkdir -p /app/data && chown -R appuser:appuser /app
USER appuser

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
