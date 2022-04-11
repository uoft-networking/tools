FROM ghcr.io/nautobot/nautobot:next-py3.10

USER 0
RUN apt-get update -y && apt-get install -y libldap2-dev libsasl2-dev libssl-dev

RUN apt-get install -y gcc && \
    apt-get autoremove -y && \
    apt-get clean all && \
    rm -rf /var/lib/apt/lists/*

RUN pip3 install --upgrade pip wheel && pip3 install django-auth-ldap debugpy django-debug-toolbar

COPY nautobot /opt/nautobot/utsc
COPY core /opt/nautobot/utsc/core
RUN pip3 install --editable /opt/nautobot/utsc
RUN pip3 install --editable /opt/nautobot/utsc/core
USER nautobot

WORKDIR /opt/nautobot