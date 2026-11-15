# Debian-based so the prebuilt aarch64 wheels of opencv-python-headless/numpy install (no compiling on the Pi).
FROM python:3.13-slim-bookworm

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    OMP_NUM_THREADS=1 \
    PYTHONPATH=/app

WORKDIR /app
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

# Staged by tools/stage_addon.py: watermeter package + meter.yaml, reference image and seed digits.
COPY app/ /app/

CMD ["python", "-m", "watermeter.service"]
