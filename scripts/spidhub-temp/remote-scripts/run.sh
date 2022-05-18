echo "= change dir"
cd hub-spid-login-ms
echo "= NEW CURRENT WORKING DIRECTORY: $(pwd)"

echo -e "\n\n\n"
echo "===                      RUN DOCKER COMPOSE                      ==="
echo "===================================================================="
docker compose -f custom-docker-compose.yml up -d