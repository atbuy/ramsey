FROM python:3.12-alpine AS base

# Python configuration
ENV PYTHONBUFFERED=true


# Install dependencies in the second stage
FROM base AS build

# Copy source
COPY . /app
WORKDIR /app

ENV PATH=/venv/bin:$PATH

# Install dependencies in a virtual environment
RUN python -m venv /venv && \
  pip install --upgrade pip setuptools wheel && \
  pip install .


# Run app in third stage
FROM base AS runtime

ENV PATH=/venv/bin:$PATH

# Copy environment from build stage
COPY --from=build /venv /venv

ENTRYPOINT [ "uvicorn", "ramsey.app:app", "--host", "0.0.0.0", "--port", "8000"]
