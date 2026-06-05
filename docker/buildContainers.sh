#!/bin/bash
##
## A simple script to build both Docker images
##
set -e
VERSION=$(python3 -c "exec(open('../src/owlplanner/version.py').read()); print(__version__)")

docker build --platform linux/amd64 --provenance=true --sbom=true --no-cache -f Dockerfile.edge -t owlplanner/owldocker:edge .
docker push owlplanner/owldocker:edge

docker build --platform linux/amd64 --provenance=true --sbom=true --no-cache -f Dockerfile.versioned -t owlplanner/owldocker:${VERSION} -t owlplanner/owldocker:latest .
docker push owlplanner/owldocker:${VERSION}
docker push owlplanner/owldocker:latest
