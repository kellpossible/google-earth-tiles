#!/bin/bash
# Download vendored dependencies

# Create directories
mkdir -p css js images

# Leaflet
curl -L -o css/leaflet.css https://cdn.jsdelivr.net/npm/leaflet@1.9.3/dist/leaflet.css
curl -L -o js/leaflet.js https://cdn.jsdelivr.net/npm/leaflet@1.9.3/dist/leaflet.js

# Leaflet images
curl -L -o images/layers.png https://cdn.jsdelivr.net/npm/leaflet@1.9.3/dist/images/layers.png
curl -L -o images/layers-2x.png https://cdn.jsdelivr.net/npm/leaflet@1.9.3/dist/images/layers-2x.png
curl -L -o images/marker-icon.png https://cdn.jsdelivr.net/npm/leaflet@1.9.3/dist/images/marker-icon.png
curl -L -o images/marker-icon-2x.png https://cdn.jsdelivr.net/npm/leaflet@1.9.3/dist/images/marker-icon-2x.png
curl -L -o images/marker-shadow.png https://cdn.jsdelivr.net/npm/leaflet@1.9.3/dist/images/marker-shadow.png

# Leaflet.Draw
curl -L -o css/leaflet.draw.css https://cdnjs.cloudflare.com/ajax/libs/leaflet.draw/1.0.2/leaflet.draw.css
curl -L -o js/leaflet.draw.js https://cdnjs.cloudflare.com/ajax/libs/leaflet.draw/1.0.2/leaflet.draw.js

# Leaflet.Draw images
curl -L -o images/spritesheet.svg https://cdnjs.cloudflare.com/ajax/libs/leaflet.draw/1.0.2/images/spritesheet.svg
curl -L -o images/spritesheet.png https://cdnjs.cloudflare.com/ajax/libs/leaflet.draw/1.0.2/images/spritesheet.png
curl -L -o images/spritesheet-2x.png https://cdnjs.cloudflare.com/ajax/libs/leaflet.draw/1.0.2/images/spritesheet-2x.png

# Fix relative paths in CSS files (images/ -> ../images/)
sed -i '' "s|url('images/|url('../images/|g" css/leaflet.draw.css
sed -i '' "s|url(images/|url(../images/|g" css/leaflet.css

echo "Dependencies downloaded!"
