FROM python:3.12-slim
WORKDIR /app
ENV PYTHONUNBUFFERED=1 BOT_DATA_DIR=/app/data
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY bot ./bot
COPY dashboard ./dashboard
RUN useradd -m bot && mkdir -p /app/data && chown bot /app/data
USER bot
ENTRYPOINT ["python", "-m", "bot"]
CMD ["paper", "--dashboard", "--host", "0.0.0.0"]
