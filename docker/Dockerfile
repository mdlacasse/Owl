# docker/Dockerfile

FROM python:3.13-slim

WORKDIR /app

RUN apt-get update; \
    apt-get upgrade; \
    apt-get install -y --no-install-recommends \
        curl \
        git \
    ; \
    rm -rf /var/lib/apt/lists/*

COPY fastentrypoint.sh /usr/bin/entrypoint.sh

RUN chmod 555 /usr/bin/entrypoint.sh

# Build in the container for faster starts.
RUN python -m pip install --no-cache-dir --upgrade pip

RUN pip install --no-cache-dir build

RUN git clone --depth 1 https://github.com/mdlacasse/Owl.git owl

RUN cd /app/owl && python -m build

RUN cd /app/owl && pip install --no-cache-dir .

EXPOSE 8501

HEALTHCHECK CMD curl --fail http://localhost:8501/_stcore/health

ENTRYPOINT ["/bin/bash", "/usr/bin/entrypoint.sh"]
