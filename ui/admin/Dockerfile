# Build stage
FROM node:20-alpine as build

WORKDIR /app

# Base path for the app (default: /admin for cloud deployment)
ARG VITE_BASE=/admin/

# Copy package files
COPY package.json package-lock.json* ./

# Install dependencies
RUN npm install

# Copy source files
COPY . .

# Build the application with base path
RUN npm run build -- --base=$VITE_BASE

# Production stage
FROM nginx:1.25-alpine

# Copy built assets from build stage
COPY --from=build /app/dist /usr/share/nginx/html

# Copy nginx configuration
COPY nginx.conf /etc/nginx/conf.d/default.conf

# Expose port
EXPOSE 80

# Health check
HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
    CMD wget -q --spider http://localhost/ || exit 1

CMD ["nginx", "-g", "daemon off;"]
