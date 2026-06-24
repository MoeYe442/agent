FROM python:3.12-slim AS builder

COPY pyproject.toml ./
COPY src/ src/

RUN pip install --no-cache-dir --target /deps -e .

FROM python:3.12-slim AS runtime

COPY --from=builder /deps /usr/local/lib/python3.12/site-packages
COPY src/ /app/src/

WORKDIR /app
EXPOSE 8000
CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000"]
