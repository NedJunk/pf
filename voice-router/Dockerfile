FROM python:3.11-slim
WORKDIR /app
COPY voice-router/ voice-router/
RUN pip install -e "voice-router/[dev]"
CMD ["pytest", "voice-router/tests/", "-v"]
