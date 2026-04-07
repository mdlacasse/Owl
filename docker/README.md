# Owl - Optimal Wealth Lab

## A retirement exploration tool based on linear programming

<img align=right src="https://raw.github.com/mdlacasse/Owl/main/papers/images/owl.png" width="250">

------------------------------------------------------------------------------------
### About
This document describes how to run Owl using a Docker container.

------------------------------------------------------------------------------------
### Running Owl without the source code
Using this approach only requires downloading the Docker image from
the [Docker Hub](http://hub.docker.com) and having the [Docker](http://docker.com)
application installed on your computer.

There are two versions of the Docker image: one that has been provisioned
with all the necessary Python modules
named 'owldocker.static' and one bare image that self-installs the Owl application from
GitHub at runtime named 'owldocker.bare'.
The 'static' version, while being larger than the 'bare' version (279 MB vs 126 MB),
will start much faster as all the required code is contained in the image. However,
the version of Owl is fixed at the time when the container was built. Conversely,
the 'bare' version will dynamically clone Owl from GitHub and download/install all its requirements.
The resulting Owl version is the one available from GitHub at the time when the container is launched.
This leads to a slower start, but this approach guarantees to have Owl's latest version.

#### Option 1: Command line

Download the image (select one from 'static' or 'bare'):
```
docker pull owlplanner/owldocker.{static or bare}
```
Then start the container:
```
docker run -p 8501:8501 --rm owlplanner/owldocker.{static or bare}
```

#### Option 2: Docker Hub website

1. Go to [hub.docker.com](https://hub.docker.com) and search for **owlplanner**.
2. Select either **owlplanner/owldocker.static** or **owlplanner/owldocker.bare**.
3. Copy the pull command shown on the page and run it in a terminal, or proceed with Docker Desktop below.

#### Option 3: Docker Desktop GUI

1. Open Docker Desktop and click on the **Search** bar at the top.
2. Search for **owlplanner/owldocker.static** (or **.bare**).
3. Click **Pull** to download the image.
4. Navigate to the **Images** tab, find the downloaded image, and click the **Run** button.
5. Expand **Optional settings** and set the **Host port** to `8501`.
6. Click **Run**.

In all cases, once the container is running, point your browser to http://localhost:8501 to access the Owl user interface.
Owl will run locally and safely through a container on your computer.

------------------------------------------------------------------------------------
### Building the docker images
This approach requires cloning the Owl package from GitHub,
and having both Python and Docker installed on your computer.

##### Building the Docker images
There are two images you can create. One builds Owl at run time, while
the other builds it statically in the image.
These two approaches trade startup time for image space
(~126 MB vs. ~279 MB, ~52 sec vs. 8 sec).
First build the Docker image from the `docker` directory:
```shell
cd docker
docker build --no-cache -f Dockerfile.{static or bare} -t owlplanner/owldocker.{static or bare}:latest .
```

#### Running the container
The container can be run directly from the command line,
with the desired port mapping.

```shell
docker run -p 8501:8501 --rm owlplanner/owldocker.{static or bare}
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
    image: owlplanner/owldocker.static   # or owlplanner/owldocker.bare
    restart: always
    ports:
      - 8501:8501
networks: {}
```
As before, just point your browser to http://localhost:8501 to access the Owl user interface.

------------------------------------------------------------------------------------

#### Credits
Josh (noimjosh@gmail.com), kg333 (matthew@kyengineer.com)
