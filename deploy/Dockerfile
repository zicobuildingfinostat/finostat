# Finostat. No dependencies, so no build stage and nothing to install.
FROM python:3.12-slim

# Deliberately no FINOSTAT_PORT here. The platform decides: Fly sets it in
# fly.toml, Railway/Render inject $PORT, and config.py falls back to 8000 for a
# plain `docker run`. Pinning it here would silently override the platform.
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    FINOSTAT_HOST=0.0.0.0

WORKDIR /app
COPY index.html og.jpg founder.jpg robots.txt sitemap.xml /app/
COPY server/ /app/server/

# Run unprivileged.
RUN useradd --system --create-home --shell /usr/sbin/nologin finostat \
    && chown -R finostat:finostat /app
USER finostat

# Documentation only; the real port comes from the environment.
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD python3 -c "import os,urllib.request,sys; p=os.environ.get('FINOSTAT_PORT') or os.environ.get('PORT') or '8000'; sys.exit(0 if urllib.request.urlopen(f'http://127.0.0.1:{p}/api/status',timeout=4).status==200 else 1)"

WORKDIR /app/server
CMD ["python3", "app.py"]
