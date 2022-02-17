echo "= change dir"
cd hub-spid-login-ms
echo "= NEW CURRENT WORKING DIRECTORY: $(pwd)"

echo -e "\n\n\n"
echo "===                   BUILD SPIDHUB APPLICATION                   ==="
echo "====================================================================="
echo ""
# idp keys are owned by root and generate problem during build.
sudo chown ec2-user conf-testenv/* 

echo "=== Build with yarn"
yarn install
yarn build

echo ""
echo "=== Build with docker"
docker compose build

echo "====================================================================="
echo "===                          INSTALL END                          ==="
echo "====================================================================="
