FROM python:3.11-slim
WORKDIR /app
COPY voice-router/ voice-router/
COPY router-service/ router-service/
RUN pip install -e "voice-router/" -e "router-service/[dev]"
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s CMD python -c \
  "import urllib.request; urllib.request.urlopen('http://localhost:8080/health')"
CMD ["uvicorn", "router_service.main:app", "--host", "0.0.0.0", "--port", "8080"]
