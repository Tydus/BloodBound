FROM python:3.5

WORKDIR /

COPY *.py start.sh requirements.txt /

COPY locale /locale

RUN pip3 install -r /requirements.txt

CMD ["/start.sh", "python3", "bot.py"]
