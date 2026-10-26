<!--
Copyright (C) 2024-2026 Martin-D. Lacasse and The Owl Authors
SPDX-License-Identifier: CC-BY-NC-SA-4.0
This documentation is licensed under Creative Commons Attribution-NonCommercial-ShareAlike 4.0; see LICENSE-docs in the repository root.
-->

# Owl - Optimal wealth lab

## A retirement exploration tool based on linear programming

<img align=right src="https://raw.githubusercontent.com/mdlacasse/Owl/main/assets/owl.png" width="350">

------------------------------------------------------------------------------------
### About
This document describes how to run Owl using a Docker container.

------------------------------------------------------------------------------------
### Running Owl without the source code
Using this approach only requires downloading the Docker image from
the [Docker Hub](https://hub.docker.com) and having the [Docker](https://docker.com)
application installed on your computer.

There are two versions of the Docker image: one versioned image (`owldocker:latest`) that has been provisioned
with all the necessary Python modules, and one edge image (`owldocker:edge`) that self-installs the Owl application from
GitHub at runtime.
The versioned image, while being larger than the edge image (264 MB vs 37 MB),
will start much faster as all the required code is contained in the image. However,
the version of Owl is fixed at the time when the container was built. Conversely,
the edge image will dynamically clone Owl from GitHub and download/install all its requirements.
The resulting Owl version is the one available from GitHub at the time when the container is launched.
This leads to a slower start, but this approach guarantees to have Owl's latest version.

The `latest` tag always points to the most recent versioned image. Specific releases are also published
under their version number (e.g. `owldocker:<version>`), so you can pin to a particular Owl release if needed.

Neither image ships MOSEK, which needs a licence: Owl runs with the free HiGHS solver in a container.
By default the app follows the light or dark theme of the system running the browser.

#### Option 1: Command line

Download the image (select one from `latest` or `edge`):
```
docker pull owlplanner/owldocker:latest
```
or
```
docker pull owlplanner/owldocker:edge
```
Then start the container:
```
docker run -p 8501:8501 --rm owlplanner/owldocker:latest
```
To force the light (or dark) theme, add `-e STREAMLIT_THEME_BASE=light` (or `dark`) to the command:
```
docker run -p 8501:8501 -e STREAMLIT_THEME_BASE=light --rm owlplanner/owldocker:latest
```
To suppress the startup disclaimer dialog, add `-e OWL_SKIP_DISCLAIMER=1`:
```
docker run -p 8501:8501 -e OWL_SKIP_DISCLAIMER=1 --rm owlplanner/owldocker:latest
```
To enable the built-in **Assistant** chat page, pass `OWL_ASSISTANT=1` and your API key
(see [info/mcp.md](https://github.com/mdlacasse/Owl/blob/main/info/mcp.md#embedded-assistant-no-mcp-client-required)
for other providers and models):
```
docker run -p 8501:8501 -e OWL_ASSISTANT=1 -e ANTHROPIC_API_KEY=sk-ant-... --rm owlplanner/owldocker:latest
```

#### Option 2: Docker Hub website

1. Go to [hub.docker.com](https://hub.docker.com) and search for **owlplanner**.
2. Select **owlplanner/owldocker** and choose the desired tag (`latest` or `edge`).
3. Copy the pull command shown on the page and run it in a terminal, or proceed with Docker Desktop below.

#### Option 3: Docker Desktop GUI

1. Open Docker Desktop and click on the **Search** bar at the top.
2. Search for **owlplanner/owldocker**.
3. Click **Pull** to download the image.
4. Navigate to the **Images** tab, find the downloaded image, and click the **Run** button.
5. Expand **Optional settings** and set the **Host port** to `8501`.
6. (Optional) To force the light theme, add an environment variable: name `STREAMLIT_THEME_BASE`, value `light`.
   To suppress the startup disclaimer dialog, add another: name `OWL_SKIP_DISCLAIMER`, value `1`.
7. Click **Run**.

In all cases, once the container is running, point your browser to http://localhost:8501 to access the Owl user interface.
Owl will run locally and safely through a container on your computer.

------------------------------------------------------------------------------------
### Building the docker images
This approach requires Docker and the `docker` directory of a clone of the Owl
repository; Python is not needed, as the images install everything they use.
Note that neither image is built from your local source: both clone `main` from GitHub
(the versioned image at build time, the edge image at each start), so local changes are
not included. Only the Dockerfiles and the entrypoint scripts are taken from your clone.

There are two images you can create. One builds Owl at run time, while
the other builds it statically in the image.
These two approaches trade startup time for image space: the edge image is small
(~37 MB) but slower to start (~52 sec), while the versioned image is larger (~264 MB)
and starts in a few seconds (~8 sec).
First build the Docker image from the `docker` directory:
```shell
cd docker
docker build --no-cache -f Dockerfile.versioned -t owlplanner/owldocker:latest .
```
or
```shell
docker build --no-cache -f Dockerfile.edge -t owlplanner/owldocker:edge .
```

#### Running the container
The container can be run directly from the command line,
with the desired port mapping.

```shell
docker run -p 8501:8501 --rm owlplanner/owldocker:latest
```

#### Running with docker-compose
Alternatively, the container can be started from the `docker` directory using `docker-compose` as follows
```shell
docker-compose up
```
The `docker-compose.yml` file shipped in the `docker` directory maps the host-side port to the container-side port:
```yml
services:
  owl:
    image: owlplanner/owldocker
    restart: always
    ports:
      - 8501:8501
networks: {}
```
An image without a tag means `latest`; write `owlplanner/owldocker:edge` for the edge image.
To force a theme, add an `environment:` entry to the service:
```yml
    environment:
      - STREAMLIT_THEME_BASE=light       # or dark; remove to follow the system theme
```
As before, just point your browser to http://localhost:8501 to access the Owl user interface.

#### Running with two themes simultaneously
To serve both a dark and a light themed instance at the same time, define two services
on different ports. Users can then bookmark their preferred URL.
```yml
services:
  owl-dark:
    image: owlplanner/owldocker:latest   # or owlplanner/owldocker:edge
    restart: always
    ports:
      - 8501:8501

  owl-light:
    image: owlplanner/owldocker:latest   # or owlplanner/owldocker:edge
    restart: always
    ports:
      - 8502:8501
    environment:
      - STREAMLIT_THEME_BASE=light
```
Point your browser to http://localhost:8501 or http://localhost:8502 depending on your preference.
Adjust port numbers as needed.

------------------------------------------------------------------------------------

#### Credits
Josh (noimjosh@gmail.com), kg333 (matthew@kyengineer.com)
