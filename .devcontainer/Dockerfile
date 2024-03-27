FROM artefact.skao.int/ska-tango-images-pytango-builder:9.4.3 AS buildenv
RUN apt-get update && apt-get install gnupg2 -y
RUN apt-get update && apt-get install libxkbcommon-x11-0 libgl1 libegl1 libwayland-client0 libwayland-server0 libxcb1 libxcb-xkb1 -y
RUN poetry self update -n 1.8.2