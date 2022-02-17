echo "= change dir"
cd hub-spid-login-ms
echo "= NEW CURRENT WORKING DIRECTORY: $(pwd)"

echo -e "\n\n\n"
echo "===                      RUN DOCKER COMPOSE                      ==="
echo "===================================================================="
docker compose up -d


echo -e "\n\n\n"
echo "===                      EXPOSE WELL_KNOWN                       ==="
echo "===================================================================="
cd well-known
docker run -d --rm -p 8080:8080 -v $(pwd):/public/.well-known/ danjellz/http-server
