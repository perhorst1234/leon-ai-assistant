# The builder supplies an already-local, content-addressed toolchain image.
ARG TOOLCHAIN_IMAGE
FROM ${TOOLCHAIN_IMAGE}

ARG BASE_COMMIT
ARG PYTEST_VERSION

LABEL org.opencontainers.image.title="leon-self-improvement-sandbox" \
      org.opencontainers.image.revision="${BASE_COMMIT}" \
      org.opencontainers.image.description="Offline, review-only validation image"

WORKDIR /app
COPY pyproject.toml /app/pyproject.toml
COPY requirements.lock /app/requirements.lock
COPY src /app/src
COPY tests /app/tests

# pytest is checked before installation: it is part of the supplied toolchain.
RUN test -n "${BASE_COMMIT}" \
 && test -n "${PYTEST_VERSION}" \
 && python3 -c 'import sys; raise SystemExit(sys.version_info < (3, 12))' \
 && EXPECTED_PYTEST_VERSION="${PYTEST_VERSION}" python3 -c 'import os, pytest; raise SystemExit(pytest.__version__ != os.environ["EXPECTED_PYTEST_VERSION"])' \
 && python3 -c 'import agents, mcp' \
 && git --version \
 && python3 -m pip --version \
 && python3 -m pip install --no-index --no-deps --no-build-isolation . \
 && chmod -R a-w /app/src \
 && test ! -w /app/src

USER 65532:65532
CMD ["python3", "-I", "-m", "pytest", "-q"]
