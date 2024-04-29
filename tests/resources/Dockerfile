FROM artefact.skao.int/ska-tango-images-pytango-builder:9.5.0 AS buildenv

RUN apt-get update && apt-get install libxkbcommon-x11-0 libgl1 libegl1 libwayland-client0 libwayland-server0 libfontconfig1 -y
RUN apt-get update && apt-get install $(apt-cache search --names-only '^libxcb.*-dev$' | awk '{ print $1 }') -y
RUN apt-get update && apt-get install xvfb -y
RUN poetry self update -n 1.8.2

# COPY --chown=tango:tango pyproject.toml poetry.lock ./

# RUN poetry config virtualenvs.create false && \
#     pip install --upgrade pip && \
#     poetry install --without docs

ENV DISPLAY=:99
RUN Xvfb :99 -screen 0 1024x768x16 &

# COPY --chown=tango:tango src ./

# USER tango

# ENV PYTHONPATH=/app/src:/usr/local/lib/python3.10/site-packages