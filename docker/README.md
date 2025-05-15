# Owl

## A retirement exploration tool based on linear programming

<img align=right src="https://raw.github.com/mdlacasse/Owl/main/docs/images/owl.png" width="250">

------------------------------------------------------------------------------------
### About
This document describes how to run Owl using a Docker container.

------------------------------------------------------------------------------------
### Run Owl without the source code
Using this approach only requires downloading the Docker image from
the [Docker Hub](http://hub.docker.com) and having the [Docker](http://docker.com)
application installed on your computer.

Downloading the Docker image from the command line:
```
docker pull owlplanner/owldocker
```
Then the container can be started (and stopped) from the command line:
```
docker run -p 8501:8501 --rm owlplanner/owldocker
```

Just point your browser to http://localhost:8501 to access the Owl user interface.
Owl will run locally and safely through a container on your computer.

One can also use the Docker Desktop graphical user interface for performing the same steps.
The image *owlplanner/owldocker* can be searched for and downloaded in the 
*Docker Hub* section of Docker Desktop. Then, on the *Images* section,
click on the run icon for the image, and use host port 8501 to map to container port 8501.

------------------------------------------------------------------------------------
### Building the docker image
This approach requires cloning the Owl package from GitHub,
and having both Python and Docker installed on your computer.

##### Docker image
There are two images you can create. One builds Owl at run time, while
the other builds it statically in the image.
These two approaches trade startup time for image space
(~300 MB vs. 1.8 GB, ~22 vs. 200 sec).
First build the Docker image from the `docker` directory:
```shell
cd docker
docker build --no-cache -f Dockerfile.{build or run} -t owldocker .
```

#### Running the container
The container can be run directly from the command line,
with the desired port mapping.

```shell
docker run -p 8501:8501 --rm owldocker
```

#### Running with docker-compose
Alternatively, the container can be started using `docker-compose` as follows
```shell
docker-compose up
```
The compose file maps the host-side port to the container-side port.
```yml
services:
  owl:
    image: owldocker
    restart: always
    ports:
      - 8501:8501
networks: {}
```
As before, just point your browser to http://localhost:8501 to access the Owl user interface.

------------------------------------------------------------------------------------

#### Credits
Josh (noimjosh@gmail.com)
