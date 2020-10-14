FROM python:3.9.0

# Force the stdout and stderr streams from python to be unbuffered.
ENV PYTHONUNBUFFERED=1

RUN pip install flask==1.1.2

WORKDIR /code

COPY app.py .

CMD ["flask", "run"]
