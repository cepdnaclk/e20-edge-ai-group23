FROM node:20-slim

# Install Node-RED globally
RUN npm install -g --unsafe-perm node-red

WORKDIR /data

# Copy package.json, flows, and settings
COPY package.json flows.json settings.js ./

# Pre-install dashboard nodes into the user directory
RUN npm install --prefix /data

EXPOSE 1880

CMD ["node-red", "--userDir", "/data", "--flowFile", "flows.json"]