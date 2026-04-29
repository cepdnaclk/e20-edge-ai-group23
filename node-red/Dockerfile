FROM node:20-slim

# Install Node-RED globally
RUN npm install -g --unsafe-perm node-red

WORKDIR /data

# Copy package.json so Node-RED auto-installs node-red-dashboard
COPY package.json ./

# Pre-install dashboard nodes into the user directory
RUN npm install --prefix /data

EXPOSE 1880

CMD ["node-red", "--userDir", "/data", "--flowFile", "flows.json"]
