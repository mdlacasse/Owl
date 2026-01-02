#!/bin/bash
##
## A simple script to build both Docker images
##
docker build --platform linux/amd64 --no-cache -f Dockerfile.bare -t owlplanner/owldocker.bare:latest .
docker push owlplanner/owldocker.bare
docker build --platform linux/amd64 --no-cache -f Dockerfile.static -t owlplanner/owldocker.static:latest .
docker push owlplanner/owldocker.static
