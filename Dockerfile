FROM python:3.11-slim

WORKDIR /app

# Install dependencies first (cached layer)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the app
COPY . .

# Init DB schema on startup, then launch
CMD python db/schema.py && uvicorn api.main:app --host 0.0.0.0 --port ${PORT:-8000}
