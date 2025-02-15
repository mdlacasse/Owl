# Owl   

## A retirement exploration tool based on linear programming

<img align=right src="https://raw.github.com/mdlacasse/Owl/main/docs/images/owl.png" width="250">

------------------------------------------------------------------------------------
### About
This is a simple docker container that downloads the latest Owl version and installs
all dependencies within a Python Virtual Environment (VENV).

------------------------------------------------------------------------------------
### Run Owl without building the container
Using this approach only requires downloading the container from the Docker Hub.
From the command line:
```
docker pull noimjosh/owldocker
```
Then run from the command line
```
docker run noimjosh/owldocker
```
or use your favorite way, from the Docker interface.

------------------------------------------------------------------------------------
### Building the container
This approach requires downloading the full Owl package.

##### Build
First build the container from the `docker` directory:
```shell
cd docker
docker build . -t owldocker
```

#### Run Using Docker Compose
Then start the service from the same directory,
```shell
docker-compose up
```
Adjust the `owl` directory mapping to a file system that can handle many files (avoid OneDrive or Dropbox).

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
This will run the service in a container. Just point your browser to http://localhost:8501.

#### Alternate Running Route
Another route is run the container from the command line,
with the desired port mapping.

```shell
cd docker
docker run -p 8501:8501 owldocker
```

------------------------------------------------------------------------------------

#### Credits
Josh (noimjosh@gmail.com)
