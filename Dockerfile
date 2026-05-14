FROM python:3.14-slim

WORKDIR /app

# Install Python dependencies
COPY backend/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy backend source
COPY backend/ ./

# Copy pre-built frontend bundle (built by: cd frontend && npm run build)
# The vite build outputs to backend/dist, so it's already included above.

# Create storage directories
RUN mkdir -p /app/config /app/data

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
