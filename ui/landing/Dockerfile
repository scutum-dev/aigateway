FROM nginx:alpine
COPY index.html /usr/share/nginx/html/index.html.template
COPY robots.txt /usr/share/nginx/html/robots.txt
COPY sitemap.xml /usr/share/nginx/html/sitemap.xml
COPY scutum-mark.svg /usr/share/nginx/html/scutum-mark.svg
COPY scutum-wordmark.svg /usr/share/nginx/html/scutum-wordmark.svg
COPY og-image.png /usr/share/nginx/html/og-image.png
# Hero demo video for the "See Scutum running. Live." section in index.html.
# ~7MB optional asset; page degrades gracefully if absent.
COPY demo-sprint-planner.mp4 /usr/share/nginx/html/demo-sprint-planner.mp4
# Real admin-ui product screenshots — used as the hero visual anchor in
# index.html (cost dashboard) and reserved for the routing-policies
# section if we wire it in later. PNG, 3000×1700, retina-quality.
COPY admin-screenshot.png /usr/share/nginx/html/admin-screenshot.png
COPY admin-routing.png /usr/share/nginx/html/admin-routing.png
COPY install.sh /usr/share/nginx/html/install.sh
COPY index.md /usr/share/nginx/html/index.md
COPY release /usr/share/nginx/html/release
COPY .well-known /usr/share/nginx/html/.well-known
COPY privacy /usr/share/nginx/html/privacy
COPY terms /usr/share/nginx/html/terms
COPY dpa /usr/share/nginx/html/dpa
COPY changelog /usr/share/nginx/html/changelog
# /try landing — kept as a .template so envsubst can interpolate TURNSTILE_SITE_KEY.
COPY try/index.html /usr/share/nginx/html/try/index.html.template
COPY nginx.conf /etc/nginx/conf.d/default.conf
# Two envsubst passes: $LITELLM_KEY into / (existing), $TURNSTILE_SITE_KEY into /try/.
RUN printf '#!/bin/sh\nenvsubst '"'"'$LITELLM_KEY'"'"' < /usr/share/nginx/html/index.html.template > /usr/share/nginx/html/index.html\nenvsubst '"'"'$TURNSTILE_SITE_KEY'"'"' < /usr/share/nginx/html/try/index.html.template > /usr/share/nginx/html/try/index.html\n' \
    > /docker-entrypoint.d/40-envsubst-html.sh && chmod +x /docker-entrypoint.d/40-envsubst-html.sh
EXPOSE 80
