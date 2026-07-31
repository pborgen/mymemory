# Deprecated for production.
#
# The web app is a static Next.js export (`output: "export"`) hosted on
# S3 + CloudFront — see infra/web_static.tf and infra/deploy-web-static.sh.
#
# This Dockerfile previously ran Next as a Node SSR service on App Runner.
# Keep only if you set deploy_web_on_apprunner=true (not recommended for cost).

FROM node:20-slim AS build
WORKDIR /app
COPY apps/web/package.json ./
RUN npm install
COPY apps/web/ ./
ARG NEXT_PUBLIC_API_URL
ENV NEXT_PUBLIC_API_URL=$NEXT_PUBLIC_API_URL
ENV NEXT_TELEMETRY_DISABLED=1
RUN npm run build

FROM nginx:alpine
COPY --from=build /app/out /usr/share/nginx/html
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
