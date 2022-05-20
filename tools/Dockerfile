FROM python:3.10

ARG uid

RUN pip install poetry
RUN mkdir /code && chmod 777 /code
RUN useradd -m -U -u ${uid} builder

USER builder
WORKDIR /code

CMD [ "poetry", "build" ]