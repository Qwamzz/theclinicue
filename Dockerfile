# Clinicue production image.
FROM python:3.12-slim AS runtime

# PYTHONUNBUFFERED keeps logs flowing to the container's stdout in real time,
# which is the only log sink available on an ephemeral filesystem (TD-01).
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    CQ_ENV=production \
    CQ_DATABASE_PATH=/data/clinicue.sqlite3 \
    PORT=8000

WORKDIR /app

# Dependencies first, so a source change does not invalidate the layer.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app
COPY wsgi.py .

# Run as an unprivileged user: a container process that does not need root
# should not have it.
RUN useradd --create-home --uid 10001 clinicue \
    && mkdir -p /data \
    && chown -R clinicue:clinicue /app /data
USER clinicue

# /data is where the SQLite file lives. Mount a persistent volume here, or the
# database is destroyed on every restart — see TD-01.
VOLUME ["/data"]

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request,os,sys; \
sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:'+os.environ.get('PORT','8000')+'/api/health', timeout=4).status==200 else 1)"

# Two workers with a threaded worker class: the workload is I/O-bound and
# SQLite serialises writes anyway, so more processes would add contention
# rather than throughput (see TD-01, TD-07).
CMD ["sh", "-c", "gunicorn --bind 0.0.0.0:${PORT} --workers 2 --threads 4 --timeout 30 --access-logfile - --error-logfile - wsgi:app"]
