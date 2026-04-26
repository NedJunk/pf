FROM python:3.11-slim
WORKDIR /app
COPY orchestrator/ orchestrator/
RUN pip install -e "orchestrator/[dev]"
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s CMD python -c \
  "import urllib.request; urllib.request.urlopen('http://localhost:8081/health')"
CMD ["uvicorn", "orchestrator.main:app", "--host", "0.0.0.0", "--port", "8081"]
