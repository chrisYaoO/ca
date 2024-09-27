FROM python:3.9



COPY . /app/

RUN apt update
RUN apt install libgl1 -y
RUN pip config set global.index-url https://mirrors.cloud.tencent.com/pypi/simple
RUN pip cache purge
RUN pip install -r /app/requirements.txt

#RUN apt install sudo -y
RUN #apt-get install redis-server -y
RUN #systemctl start docker

WORKDIR /app/

CMD ["python", "client.py"]