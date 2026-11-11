# App web: se compila con Node y se sirve con nginx. Se construye desde app/.
FROM node:24-alpine AS compilacion
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci
COPY . .
RUN npm run build

FROM nginx:1.29-alpine
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=compilacion /app/dist/app/browser /usr/share/nginx/html
EXPOSE 80
