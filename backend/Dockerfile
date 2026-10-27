# One image, three roles: the API (default CMD), a Celery worker, and Celery beat. Override the command per service.
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1 PYTHONPATH=/srv ENABLE_DOCS=false
WORKDIR /srv

# Layer caching: dependencies change rarely, code often. Install ONLY the dependency list from pyproject.toml
# first (the project itself is run from /srv, never pip-installed), so a code edit doesn't re-download wheels.
COPY pyproject.toml ./
RUN python -c "import tomllib; print('\n'.join(tomllib.load(open('pyproject.toml','rb'))['project']['dependencies']))" > /tmp/requirements.txt \
 && pip install -r /tmp/requirements.txt && rm /tmp/requirements.txt

COPY app ./app
COPY sources ./sources
COPY curriculum ./curriculum

# Never run as root in a container.
RUN useradd --system --uid 10001 --no-create-home app && chown -R app /srv
USER app

EXPOSE 8000
# Platforms like Render/Railway/Fly inject $PORT; fall back to 8000 elsewhere. `exec` makes uvicorn PID 1 so it
# receives SIGTERM and drains in-flight requests on deploys.
CMD ["sh", "-c", "exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --proxy-headers --forwarded-allow-ips='*'"]
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
  CMD python -c "import os,urllib.request; urllib.request.urlopen(f'http://127.0.0.1:{os.environ.get(\"PORT\",\"8000\")}/health', timeout=4)"
