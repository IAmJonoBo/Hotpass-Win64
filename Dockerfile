# syntax=docker/dockerfile:1.19

FROM mambaorg/micromamba:2.3.3

USER root

ARG PYTHON_VERSION=3.13
ARG UV_VERSION=0.9.5
ARG UV_SHA256_X86_64=2cf10babba653310606f8b49876cfb679928669e7ddaa1fb41fb00ce73e64f66
ARG UV_SHA256_AARCH64=9db0c2f6683099f86bfeea47f4134e915f382512278de95b2a0e625957594ff3
ARG TARGETARCH
ARG APP_USER=hotpass
ARG APP_UID=10001
ARG APP_GID=10001
ARG HOTPASS_UV_EXTRAS="dev orchestration enrichment geospatial compliance dashboards"

ENV APP_USER=${APP_USER}
ENV APP_HOME=/home/${APP_USER}
ENV APP_UID=${APP_UID}
ENV APP_GID=${APP_GID}
ENV HOTPASS_UV_EXTRAS=${HOTPASS_UV_EXTRAS}
ENV UV_PROJECT_ENVIRONMENT=/opt/hotpass/.venv
ENV UV_LINK_MODE=copy
ENV UV_COMPILE_BYTECODE=1
ENV UV_CACHE_DIR=${APP_HOME}/.cache/uv
ENV PYTHONUNBUFFERED=1
ENV PIP_DISABLE_PIP_VERSION_CHECK=1
ENV PATH=/opt/hotpass/.venv/bin:/usr/local/bin:/opt/conda/bin:${APP_HOME}/.local/bin:/usr/sbin:/usr/bin:/sbin:/bin

SHELL ["/bin/bash", "-o", "pipefail", "-c"]

RUN set -eux; \
    micromamba install -y -n base "python=${PYTHON_VERSION}" curl -c conda-forge; \
    micromamba clean --all --yes

RUN set -eux; \
    case "${TARGETARCH}" in \
        amd64) uv_arch="x86_64"; uv_sha="${UV_SHA256_X86_64}";; \
        arm64) uv_arch="aarch64"; uv_sha="${UV_SHA256_AARCH64}";; \
        *) echo "Unsupported TARGETARCH: ${TARGETARCH}" >&2; exit 1;; \
    esac; \
    curl -LsSf -o /tmp/uv.tar.gz "https://github.com/astral-sh/uv/releases/download/${UV_VERSION}/uv-${uv_arch}-unknown-linux-gnu.tar.gz"; \
    echo "${uv_sha}  /tmp/uv.tar.gz" | sha256sum -c -; \
    tar -xzf /tmp/uv.tar.gz -C /usr/local/bin --strip-components=1 \
        "uv-${uv_arch}-unknown-linux-gnu/uv" \
        "uv-${uv_arch}-unknown-linux-gnu/uvx"; \
    chmod +x /usr/local/bin/uv /usr/local/bin/uvx; \
    rm /tmp/uv.tar.gz

RUN set -eux; \
    groupadd --system --gid "${APP_GID}" "${APP_USER}"; \
    useradd --system --create-home --uid "${APP_UID}" --gid "${APP_GID}" "${APP_USER}"

RUN set -eux; \
    install -d -m 0755 -o "${APP_UID}" -g "${APP_GID}" /app /opt/hotpass "${APP_HOME}/.cache/uv"

WORKDIR /app

COPY --link --chown=${APP_UID}:${APP_GID} . .

USER ${APP_USER}

RUN --mount=type=cache,target=${UV_CACHE_DIR},uid=${APP_UID},gid=${APP_GID} \
    set -eux; \
    extras=${HOTPASS_UV_EXTRAS:-"dev orchestration"}; \
    if [[ -z ${extras// /} ]]; then \
        echo "HOTPASS_UV_EXTRAS is empty; refusing to build without at least one extra." >&2; \
        exit 1; \
    fi; \
    declare -a args=(); \
    for extra in ${extras}; do \
        args+=("--extra" "${extra}"); \
    done; \
    echo "Synchronising uv environment with extras: ${extras}"; \
    uv sync --frozen --no-editable "${args[@]}"

RUN --mount=type=cache,target=${UV_CACHE_DIR},uid=${APP_UID},gid=${APP_GID} \
    set -eux; \
    uv pip check; \
    uv run hotpass --help >/dev/null

HEALTHCHECK --interval=1m --timeout=10s --start-period=30s --retries=3 \
  CMD uv run hotpass --help >/dev/null 2>&1 || exit 1

ENTRYPOINT ["uv", "run", "hotpass"]
CMD ["--help"]
