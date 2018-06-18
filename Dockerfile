FROM python:3.5

RUN apt-get -y update && apt-get -y install easy-rsa && rm -rf /var/lib/apt/lists/* /var/cache/apt/archives/*

WORKDIR /

COPY *.py start.sh requirements.txt /

RUN pip3 install -r /requirements.txt

CMD ["start.sh", "python3", "bot.py"]
