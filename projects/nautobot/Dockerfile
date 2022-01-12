FROM ubuntu:hirsute

RUN apt-get update -y && \
    apt-get install -y \
    openssl build-essentials libxmlsec1-dev libxmlsec1-openssl pkg-config \
    libldap-dev libsasl2-dev libmariadb-dev git mime-support curl libxml2 \
    libmariadb3 libldap2-dev libsasl2-dev libssl-dev && \
    apt-get autoremove -y && \
    apt-get clean all

RUN 

RUN update-alternatives --install /usr/bin/python3 python3 /usr/bin/python3.10 1 &&\
    update-alternatives --install /usr/bin/python3 python3 /usr/bin/python3.10 1 &&\
    update-alternatives --install /usr/bin/python python /usr/bin/python3 1

# Modify the PATH here because otherwise poetry fails 100% of the time. WAT??
ENV PATH="${PATH}:/root/.local/bin"

# Install Poetry manually from GitHub because otherwise it installs its own
# dependencies globally which may conflict with ours.
# https://python-poetry.org/docs/#osx-linux-bashonwindows-install-instructions
RUN curl -sSL https://raw.githubusercontent.com/python-poetry/poetry/master/install-poetry.py -o /tmp/install-poetry.py && \
    python /tmp/install-poetry.py && \
    rm -f /tmp/install-poetry.py

RUN pip3 install --upgrade pip wheel && pip3 install pyuwsgi django-auth-ldap

# Make sure we don't run as a root user
RUN useradd --system --shell /bin/bash --create-home --home-dir /opt/nautobot nautobot

USER nautobot