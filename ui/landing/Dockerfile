FROM nginx:alpine
COPY index.html /usr/share/nginx/html/index.html.template
RUN printf '#!/bin/sh\nenvsubst '"'"'$LITELLM_KEY'"'"' < /usr/share/nginx/html/index.html.template > /usr/share/nginx/html/index.html\n' \
    > /docker-entrypoint.d/40-envsubst-html.sh && chmod +x /docker-entrypoint.d/40-envsubst-html.sh
EXPOSE 80
