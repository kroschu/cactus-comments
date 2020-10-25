FROM python:3.9.0

# Force the stdout and stderr streams from python to be unbuffered.
ENV PYTHONUNBUFFERED=1

RUN pip install flask==1.1.2 pytest==6.1.1 requests==2.24.0

WORKDIR /code

COPY test_app.py .
COPY app.py .

CMD ["flask", "run"]
