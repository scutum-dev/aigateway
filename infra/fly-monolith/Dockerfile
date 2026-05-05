# Scutum monolith image — runs the full stack inside a single Fly machine.
#
# Layered on top of docker:dind so we can re-use the customer release compose
# unchanged. On boot the entrypoint starts dockerd, runs the same install
# flow customers run on a fresh VM, then `scutum up`s the stack and tails the
# combined logs. Front-of-house nginx (also inside the machine) maps:
#
#   GET /                → admin-ui:80   (the React app)
#   GET /api/*           → admin-api:8086
#   GET /v1/*            → litellm:4000  (OpenAI-compatible proxy)
#   GET /docs/*          → docs-site:80  (mkdocs)
#
# The whole thing fits in a 2 GB Fly machine because postgres + redis +
# litellm + admin-api + admin-ui + nginx all share one OS. Cold-start
# (machine wake from auto-stop) is ~30-60 s while dockerd + containers boot.
FROM docker:27-dind

# Tools we need: bash for the install script, curl for fetching artifacts,
# nginx for the per-trial reverse proxy, plus standard coreutils.
RUN apk add --no-cache bash curl ca-certificates nginx fuse-overlayfs e2fsprogs

# Bundle the same release compose + installer the customers get. SCUTUM_VERSION
# pins to whatever was current at image build time; can be overridden at run.
ARG SCUTUM_VERSION=0.1.0
ENV SCUTUM_VERSION=${SCUTUM_VERSION}

WORKDIR /app
COPY entrypoint.sh /app/entrypoint.sh
COPY nginx.conf /etc/nginx/nginx.conf
COPY welcome.html /var/www/welcome/index.html
RUN chmod +x /app/entrypoint.sh

# /var/lib/docker is a Fly volume mount target; postgres/redis state lives
# there under their respective named volumes inside the dind daemon.
VOLUME /var/lib/docker
VOLUME /etc/scutum

EXPOSE 80
ENTRYPOINT ["/app/entrypoint.sh"]
