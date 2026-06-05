::
:: A simple script to build both Docker images
::
for /f "tokens=2 delims==" %%V in ('findstr __version__ ..\src\owlplanner\version.py') do set VERSION=%%V
set VERSION=%VERSION: =%
set VERSION=%VERSION:"=%

docker build --provenance=true --sbom=true --no-cache -f Dockerfile.edge -t owlplanner/owldocker:edge .
docker push owlplanner/owldocker:edge

docker build --provenance=true --sbom=true --no-cache -f Dockerfile.versioned -t owlplanner/owldocker:%VERSION% -t owlplanner/owldocker:latest .
docker push owlplanner/owldocker:%VERSION%
docker push owlplanner/owldocker:latest
