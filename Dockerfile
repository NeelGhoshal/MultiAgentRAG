FROM python:3.12-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
# Build the vector store into the image. This also caches Chroma's embedding model, so queries need no download.
RUN python -m tutor.ingest

ENV STREAMLIT_SERVER_HEADLESS=true \
    STREAMLIT_BROWSER_GATHER_USAGE_STATS=false
CMD streamlit run app.py --server.address 0.0.0.0 --server.port ${PORT:-8501}
