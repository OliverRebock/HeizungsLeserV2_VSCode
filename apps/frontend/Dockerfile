FROM node:20-alpine AS base

WORKDIR /app

COPY package*.json ./
RUN npm install

FROM base AS dev

ENV HOST=0.0.0.0
ENV PORT=3000

EXPOSE 3000

CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0", "--port", "3000"]

FROM base AS build

# Wir definieren das ARG, das während des Builds gesetzt wird
ARG VITE_API_BASE_URL
# Wir setzen die ENV-Variable für den Vite-Build-Prozess
ENV VITE_API_BASE_URL=$VITE_API_BASE_URL

COPY . .
	RUN npm run build

# Produktions-Stage
FROM nginx:stable-alpine AS production

COPY --from=build /app/dist /usr/share/nginx/html
# Kopiere eine nginx-Konfiguration für SPA-Routing
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
