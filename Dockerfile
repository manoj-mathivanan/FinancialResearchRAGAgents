FROM node:24-bookworm-slim AS web-build
WORKDIR /build
COPY web/package.json web/package-lock.json ./
RUN npm ci
COPY web/ ./
RUN npm run build

FROM python:3.13-slim-bookworm
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
WORKDIR /app
RUN apt-get update \
    && apt-get install -y --no-install-recommends poppler-utils \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --create-home --uid 10001 findoc
COPY requirements-*.txt ./
RUN pip install --no-cache-dir -r requirements-web.txt
COPY findoc/ findoc/
COPY data/infosys-*.json data/
COPY --from=web-build /build/dist web/dist
USER findoc
CMD ["sh", "-c", "exec python -m uvicorn findoc.api:app --host 0.0.0.0 --port \"${PORT:-8080}\""]
