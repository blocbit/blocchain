FROM python:3.7-slim-buster 

ADD . /

RUN pip install -r requirements.txt

CMD [ "python", "./node.py" ]
