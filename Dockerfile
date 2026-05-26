FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .

RUN uv sync --frozen

COPY . .

EXPOSE 8000