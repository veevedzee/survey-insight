# Backend image for Hugging Face Spaces (free CPU tier: 2 vCPU, 16 GB RAM).
# Build from the repository root:  docker build -t survey-insight-api .
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    HF_HOME=/app/.cache/huggingface \
    SAMPLE_DATA_PATH=/app/sample_data/student_wellbeing_survey.csv \
    PORT=7860

# Hugging Face Spaces run containers as user id 1000.
RUN useradd --create-home --uid 1000 app
WORKDIR /app

# CPU-only PyTorch: about 200 MB instead of about 2 GB with GPU (CUDA) support,
# which free hosting doesn't have anyway. Installed first so Docker caches it.
RUN pip install "torch~=2.15.0" --index-url https://download.pytorch.org/whl/cpu

COPY backend/requirements.txt backend/requirements.txt
RUN pip install -r backend/requirements.txt

# Download the embedding model at build time and bake it into the image, so a
# cold start doesn't spend a minute downloading 470 MB.
RUN python -c "from sentence_transformers import SentenceTransformer; \
SentenceTransformer('sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2')"

COPY backend/survey_insight backend/survey_insight
COPY sample_data/student_wellbeing_survey.csv sample_data/student_wellbeing_survey.csv
RUN chown -R app:app /app

USER app
WORKDIR /app/backend
EXPOSE 7860
CMD ["sh", "-c", "uvicorn survey_insight.api:app --host 0.0.0.0 --port ${PORT}"]
