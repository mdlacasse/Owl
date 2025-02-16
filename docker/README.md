# Owl

## A retirement exploration tool based on linear programming

<img align=right src="https://raw.github.com/mdlacasse/Owl/main/docs/images/owl.png" width="250">

------------------------------------------------------------------------------------
### About
This document describes how to run Owl using a Docker container.
This simple container downloads the latest Owl version and installs
all dependencies within a Python Virtual Environment (VENV).

------------------------------------------------------------------------------------
### Run Owl without building the Docker image - Currently broken on some OS
Using this approach only requires downloading the Docker image from
the [Docker Hub](http://hub.docker.com) and having the [Docker](http://docker.com)
application installed on your computer.

Downloading the Docker image from the command line:
```
docker pull noimjosh/owldocker
```
Then the container can be started from the command line:
```
docker run -p 8501:8501 --rm noimjosh/owldocker
```
One can also use the Docker graphical user interface for performing the same steps. This is not covered here.

------------------------------------------------------------------------------------
### Building the docker image
This approach requires cloning the full Owl package from GitHub,
and having Python and Docker installed on your computer.

##### Docker image
First build the Docker image from the `docker` directory:
```shell
cd docker
docker build -t owldocker .
```

#### Run using docker-compose
Then start the service from the same directory using `docker-compose`,
```shell
docker-compose up
```
Adjust the `volumes:` mapping to a directory on a file system that can handle many files
(avoid OneDrive or Dropbox file systems).

```yml
services:
  owl:
    image: owldocker
    restart: always
    ports:
      - 8501:8501
    volumes:
      - /tmp/owl:/app
networks: {}
```
This will run the service in a container.
Just point your browser to http://localhost:8501 to access the Owl user interface.
Owl will run locally and safely through a container on your computer.

#### Alternate running route
Another route is to run the container directly from the command line,
with the desired port mapping.

```shell
docker run -p 8501:8501 --rm owldocker
```

------------------------------------------------------------------------------------

#### Credits
Josh (noimjosh@gmail.com)
