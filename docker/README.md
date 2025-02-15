# Owl   

## A retirement exploration tool based on linear programming

<img align=right src="https://raw.github.com/mdlacasse/Owl/main/docs/images/owl.png" width="250">

------------------------------------------------------------------------------------
### About
This is a simple docker container that downloads the latest Owl version and installs
all dependencies within a Python Virtual Environment (VENV).

------------------------------------------------------------------------------------
### Docker Compose
To start,
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

------------------------------------------------------------------------------------
### Alternate Route
Another route is to build the container and run it from the command line,
with the desired port mapping.

#### Build
```shell
cd docker
docker build . -t owldocker
```

#### Run
```shell
cd docker
docker run -p 8501:8501 owldocker
```

------------------------------------------------------------------------------------

#### Credits
Josh (noimjosh@gmail.com)
