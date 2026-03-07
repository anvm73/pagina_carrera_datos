FROM node:20-alpine AS build

ARG PUBLIC_PROJECTS_API_URL=/api
ARG PUBLIC_CHATBOT_API_URL=/api/chat

ENV PUBLIC_PROJECTS_API_URL=${PUBLIC_PROJECTS_API_URL} \
    PUBLIC_CHATBOT_API_URL=${PUBLIC_CHATBOT_API_URL}

WORKDIR /app

COPY package*.json ./
RUN npm ci

COPY . .
RUN npm run build

FROM nginx:1.27-alpine

COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
