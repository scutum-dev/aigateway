FROM nginx:alpine
COPY index.html /usr/share/nginx/html/index.html.template
COPY robots.txt /usr/share/nginx/html/robots.txt
COPY sitemap.xml /usr/share/nginx/html/sitemap.xml
COPY scutum-mark.svg /usr/share/nginx/html/scutum-mark.svg
COPY scutum-wordmark.svg /usr/share/nginx/html/scutum-wordmark.svg
COPY og-image.png /usr/share/nginx/html/og-image.png
COPY install.sh /usr/share/nginx/html/install.sh
COPY release /usr/share/nginx/html/release
COPY privacy /usr/share/nginx/html/privacy
COPY terms /usr/share/nginx/html/terms
COPY dpa /usr/share/nginx/html/dpa
COPY changelog /usr/share/nginx/html/changelog
COPY nginx.conf /etc/nginx/conf.d/default.conf
RUN printf '#!/bin/sh\nenvsubst '"'"'$LITELLM_KEY'"'"' < /usr/share/nginx/html/index.html.template > /usr/share/nginx/html/index.html\n' \
    > /docker-entrypoint.d/40-envsubst-html.sh && chmod +x /docker-entrypoint.d/40-envsubst-html.sh
EXPOSE 80
