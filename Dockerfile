# merch7am API - FastAPI backend
# Build: docker build -t merch7am-api .
# Run:   docker run -p 3001:3001 --env-file .env merch7am-api

FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY lib/ ./lib/
COPY routes/ ./routes/
COPY main.py .

# Create data directory (estimates - ephemeral unless using EFS)
RUN mkdir -p data/estimates

# Port
ENV PORT=3001
EXPOSE 3001

# Run with uvicorn
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "3001"]
