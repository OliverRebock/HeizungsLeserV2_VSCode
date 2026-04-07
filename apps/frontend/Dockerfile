FROM node:20-alpine AS build

WORKDIR /app

# Wir definieren das ARG, das während des Builds gesetzt wird
ARG VITE_API_BASE_URL
# Wir setzen die ENV-Variable für den Vite-Build-Prozess
ENV VITE_API_BASE_URL=$VITE_API_BASE_URL

COPY package*.json ./
RUN npm install

COPY . .
RUN npm run build

# Produktions-Stage
FROM nginx:stable-alpine

COPY --from=build /app/dist /usr/share/nginx/html
# Kopiere eine nginx-Konfiguration für SPA-Routing
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
