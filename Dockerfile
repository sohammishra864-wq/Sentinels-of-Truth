FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY main.py .
COPY backend/database/schema.sql .
COPY backend/ ./backend/
COPY frontend/ ./frontend/

RUN mkdir -p database

EXPOSE 8000

# this port is differnt than mine that was local
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]