# Finostat. No dependencies, so no build stage and nothing to install.
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    FINOSTAT_HOST=0.0.0.0 \
    FINOSTAT_PORT=8000

WORKDIR /app
COPY index.html og.jpg robots.txt sitemap.xml /app/
COPY server/ /app/server/

# Run unprivileged.
RUN useradd --system --create-home --shell /usr/sbin/nologin finostat \
    && chown -R finostat:finostat /app
USER finostat

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD python3 -c "import os,urllib.request,sys; p=os.environ.get('FINOSTAT_PORT') or os.environ.get('PORT') or '8000'; sys.exit(0 if urllib.request.urlopen(f'http://127.0.0.1:{p}/api/status',timeout=4).status==200 else 1)"

WORKDIR /app/server
CMD ["python3", "app.py"]
