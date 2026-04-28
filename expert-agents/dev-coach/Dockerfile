FROM python:3.11-slim
WORKDIR /app
COPY expert-agents/base/ expert-agents/base/
COPY expert-agents/dev-coach/ expert-agents/dev-coach/
RUN pip install -e "expert-agents/base/" -e "expert-agents/dev-coach/[dev]"
COPY expert-agents/dev-coach/wiki_schema.md /app/wiki_schema.md
HEALTHCHECK --interval=30s --timeout=5s CMD python -c \
  "import urllib.request; urllib.request.urlopen('http://localhost:8082/health')"
CMD ["uvicorn", "dev_coach.main:app", "--host", "0.0.0.0", "--port", "8082"]
