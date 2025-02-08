# Owl   

## A retirement exploration tool based on linear programming

<img align=right src="https://raw.github.com/mdlacasse/Owl/main/docs/images/owl.png" width="250">

---
### About
This is a simple docker container that downloads the latest Owl version and installs all dependencies within a Python Virtual Environment (VENV).

---

### Build
```
cd docker
docker build . -t owldocker
```


---

### Docker Compose
```
services:
  owl:
    image: owldocker
    restart: always
    ports:
      - 8501:8501
    volumes:
      - ./config:/app
networks: {}
```
------------------------------------------------------------------------------------
