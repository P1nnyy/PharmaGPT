# Base Image
FROM node:18-bullseye-slim

# Set Working Directory
WORKDIR /app

# Install System Dependencies (if needed for canvas/pdf parsing)
# RUN apt-get update && apt-get install -y ...

# Copy Package Files
COPY package.json package-lock.json ./

# Install Dependencies
RUN npm install --omit=dev

# Copy Source Code
COPY src/ ./src/

# Environment Variables
ENV PORT=8000
ENV NODE_ENV=production

# Expose Port
EXPOSE 8000

# Run Command
CMD ["npm", "start"]
