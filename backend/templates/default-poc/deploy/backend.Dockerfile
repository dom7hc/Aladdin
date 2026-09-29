# Builds the AI-generated PoC backend (Backend Plan §10 preview deployment).
# Build context is the generated source root (backend/, frontend/, deploy/).
FROM python:3.12-slim

WORKDIR /app

COPY backend/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/ ./

EXPOSE 8000
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
