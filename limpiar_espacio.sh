#!/bin/bash

echo "=== Limpieza de recursos Docker no utilizados ==="
sudo docker system prune -a -f

echo "=== Limpieza de volúmenes Docker no utilizados ==="
sudo docker volume prune -f

echo "=== Limpieza de builder cache de Docker ==="
sudo docker builder prune -a -f

echo "=== Espacio ocupado por Docker ==="
sudo du -sh /var/lib/docker

echo "=== Archivos más grandes en el sistema (TOP 20) ==="
sudo du -ahx / | sort -rh | head -20

echo "=== Espacio libre en disco ==="
df -h