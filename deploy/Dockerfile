FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    HOSTTALK_HOME=/data

WORKDIR /app
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY hosttalk ./hosttalk
COPY static ./static
COPY templates ./templates
COPY server.py ./
COPY deploy/docker-entrypoint.sh /usr/local/bin/hosttalk-start
RUN chmod +x /usr/local/bin/hosttalk-start && mkdir -p /data && chown -R 10001:10001 /data

USER 10001:10001
EXPOSE 7284
VOLUME ["/data"]
HEALTHCHECK --interval=30s --timeout=4s --start-period=10s \
  CMD python -c "import urllib.request;urllib.request.urlopen('http://127.0.0.1:7284/healthz',timeout=3)"

ENTRYPOINT ["hosttalk-start"]
