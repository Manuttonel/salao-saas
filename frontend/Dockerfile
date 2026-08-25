FROM node:20-alpine

WORKDIR /app

COPY package*.json ./
RUN npm install

COPY . .

EXPOSE 5173

# --host é necessário para o servidor do Vite aceitar conexões vindas
# de fora do container (senão só aceita "localhost" dentro dele mesmo).
CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0"]
