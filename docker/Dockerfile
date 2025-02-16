# app/Dockerfile

FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y \
    git \
    python3-pip \
    && rm -rf /var/lib/apt/lists/*

COPY entrypoint.sh /usr/bin/entrypoint.sh

RUN chmod 555 /usr/bin/entrypoint.sh

# Uncomment below to build into the container
# The entrypoint.sh builds the runtime environment
#RUN git clone https://github.com/mdlacasse/Owl.git .

#RUN python -m build

#RUN pip3 install .

EXPOSE 8501

HEALTHCHECK CMD curl --fail http://localhost:8501/_stcore/health

ENTRYPOINT ["/bin/bash", "/usr/bin/entrypoint.sh"]
