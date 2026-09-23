# Stage 1: Building the code
FROM node:20-alpine AS builder
WORKDIR /frontend
ARG NEXT_PUBLIC_API_URL
ENV NEXT_PUBLIC_API_URL=$NEXT_PUBLIC_API_URL
COPY package.json package-lock.json ./
RUN npm install
COPY . .
RUN npm run build

# Stage 2: Run the code
FROM node:20-alpine
WORKDIR /frontend
COPY --from=builder /frontend/.next ./.next
COPY --from=builder /frontend/public ./public
COPY --from=builder /frontend/package.json ./package.json
COPY --from=builder /frontend/node_modules ./node_modules
COPY --from=builder /frontend/next.config.js ./next.config.js
COPY --from=builder /frontend/start.sh ./start.sh

RUN chmod +x start.sh

EXPOSE 3000
CMD ["./start.sh"]
