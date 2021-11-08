FROM python:3.9.5-buster

# Force the stdout and stderr streams from python to be unbuffered.
ENV PYTHONUNBUFFERED=1

COPY requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt

WORKDIR /code

COPY test_app.py .
COPY app.py .

CMD ["gunicorn", "-w", "1", "-b", "0.0.0.0:5000", "--timeout", "500", "app:create_app_from_env()"]
