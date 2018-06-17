FROM python:3.5

WORKDIR /

COPY requirements.txt /

RUN pip3 install -r /requirements.txt

COPY *.py /

COPY locale /locale

CMD ["python3", "bot.py"]
