FROM python:3.12-slim

WORKDIR /app

# 依存パッケージを先にインストール（レイヤーキャッシュ活用）
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# ソースコードをコピー
COPY src/ ./src/

# SQLite保存用ディレクトリを作成
RUN mkdir -p /app/data

EXPOSE 8000

CMD uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000} --app-dir src
