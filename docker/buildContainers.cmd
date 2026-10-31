::
:: A simple script to build both Docker images
::
for /f "tokens=2 delims==" %%V in ('findstr __version__ ..\src\owlplanner\version.py') do set VERSION=%%V
set VERSION=%VERSION: =%
set VERSION=%VERSION:"=%

docker buildx build --platform linux/amd64,linux/arm64 --provenance=true --sbom=true --no-cache -f Dockerfile.edge -t owlplanner/owldocker:edge --push .

docker buildx build --platform linux/amd64,linux/arm64 --provenance=true --sbom=true --no-cache -f Dockerfile.versioned -t owlplanner/owldocker:%VERSION% -t owlplanner/owldocker:latest --push .
