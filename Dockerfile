# One image for both Railway services (api + ui). They share this build and differ only by the start
# command, which each service overrides via railway.{api,ui}.toml [deploy].startCommand.
#
# Why a Dockerfile instead of Railpack autodetect: Railpack builds in one (mise) image and runs in a
# separate runtime image, and a plain `pip install .` lands in the build image's global site-packages,
# which the runtime image does not carry over -> "No module named uvicorn" at start (verified 2026-06-20).
# Here there is a single interpreter: the python that installs the deps is the python that runs them.
FROM python:3.12-slim

WORKDIR /app

# Copy the whole repo first: hatchling needs the source tree (src/ layout) to build the wheel, and the
# api needs the committed corpus/ at runtime to build the Chroma index on first boot.
COPY . .
RUN pip install --no-cache-dir .

# Default command is the api (the ui service overrides it). The script runs in a shell so $PORT
# expands even when Railway exec's the start command directly. See bin/start-*.sh.
CMD ["sh", "bin/start-api.sh"]
