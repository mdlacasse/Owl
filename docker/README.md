# Owl   

## A retirement exploration tool based on linear programming

<img align=right src="https://raw.github.com/mdlacasse/Owl/main/docs/images/owl.png" width="250">

------------------------------------------------------------------------------------
### About
This is a simple docker container that downloads the latest Owl version and installs
all dependencies within a Python Virtual Environment (VENV).

------------------------------------------------------------------------------------
### Run Owl without building the container
Using this approach only requires downloading the container from the [Docker Hub](http://hub.docker.com) and having [Docker](http://docker.com) installed on your computer.

Downloading image from the command line:
```
docker pull noimjosh/owldocker
```
Then running from the command line:
```
docker run -p 8501:8501 noimjosh/owldocker
```
or use the Docker graphical user interface for performing the same steps.

------------------------------------------------------------------------------------
### Building the docker image
This approach requires cloning the full Owl package from GitHub, and having Python and Docker installed on your computer.

##### Docker image
First build the image from the `docker` directory:
```shell
cd docker
docker build . -t owldocker
```

#### Run Using Docker Compose
Then start the service from the same directory,
```shell
docker-compose up
```
Adjust the `volume:` directory mapping to a file system that can handle many files (avoid OneDrive or Dropbox file systems).

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
This will run the service in a container. Just point your browser to http://localhost:8501 to access the `Owl` interface.

#### Alternate Running Route
Another route is run the container directly from the command line,
with the desired port mapping.

```shell
cd docker
docker run -p 8501:8501 owldocker
```

------------------------------------------------------------------------------------

#### Credits
Josh (noimjosh@gmail.com)
