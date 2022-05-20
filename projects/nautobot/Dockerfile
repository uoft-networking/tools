FROM python:3.10

RUN pip install poetry
RUN apt-get install -y gcc libldap2-dev libsasl2-dev libssl-dev && \
    apt-get autoremove -y && \
    apt-get clean all && \
    rm -rf /var/lib/apt/lists/*

RUN pip3 install --upgrade pip wheel && pip3 install django-auth-ldap debugpy django-debug-toolbar

COPY nautobot /opt/nautobot/utsc
COPY core /opt/nautobot/utsc/core
RUN pip3 install --editable /opt/nautobot/utsc
RUN pip3 install --editable /opt/nautobot/utsc/core
USER nautobot


WORKDIR /code