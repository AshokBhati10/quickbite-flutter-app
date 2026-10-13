FROM python:3.12-slim-bookworm

WORKDIR /srv/app

COPY requirements.txt requirements.lock ./
RUN pip install --no-cache-dir -r requirements.lock

COPY app ./app
COPY workers ./workers
COPY migrations ./migrations
COPY alembic.ini ./
COPY pytest.ini ./

EXPOSE 8000
