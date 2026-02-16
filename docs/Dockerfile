FROM python:3.12-alpine AS builder
WORKDIR /docs
RUN pip install --no-cache-dir mkdocs-material
COPY mkdocs.yml .
COPY docs/ docs/
RUN mkdocs build --strict

FROM nginx:alpine
COPY --from=builder /docs/site /usr/share/nginx/html
EXPOSE 80
