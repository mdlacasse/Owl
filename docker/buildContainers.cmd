::
:: A simple script to build both Docker images
::
docker build --provenance=true --sbom=true --no-cache -f Dockerfile.bare -t owlplanner/owldocker.bare:latest .
docker push owlplanner/owldocker.bare
docker build --provenance=true --sbom=true --no-cache -f Dockerfile.static -t owlplanner/owldocker.static:latest .
docker push owlplanner/owldocker.static
