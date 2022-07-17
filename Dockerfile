FROM python:3.9-slim
RUN apt-get update && apt-get upgrade -y

RUN adduser kak

WORKDIR /home/kak

COPY requirements.txt requirements.txt
RUN pip install -r requirements.txt && pip install gunicorn


COPY main.py ./



ENV FLASK_APP main.py

RUN chown -R kak:kak ./
USER kak

EXPOSE 8080

CMD exec gunicorn --bind :8080 --workers 1 main:app