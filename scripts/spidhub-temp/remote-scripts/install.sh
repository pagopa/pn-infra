echo -e "\n\n\n"
echo "===              INSTALL REQUIRED SOFTWARE PACKAGES              ==="
echo "===================================================================="
echo ""
echo "=== Update package repository"

sudo yum update -y

echo ""
echo "=== Install git from yum"
sudo yum install -y git

echo ""
echo "=== Install java from amazon-linux-extras"
sudo amazon-linux-extras install -y java-openjdk11

echo ""
echo "=== Install docker from amazon-linux-extras"
sudo amazon-linux-extras install docker

echo ""
echo "=== Install docker from yum"
sudo yum install -y docker

echo ""
echo "=== Activate docker service"
echo "= start"
sudo service docker start
echo "= enable"
sudo systemctl enable docker
echo "= usermod"
sudo usermod -a -G docker ec2-user
echo "= info"
sudo docker info


echo "= download plugin"
mkdir -p ~/.docker/cli-plugins/
curl -SL https://github.com/docker/compose/releases/download/v2.2.3/docker-compose-linux-x86_64 -o ~/.docker/cli-plugins/docker-compose
chmod +x ~/.docker/cli-plugins/docker-compose

echo ""
echo "=== Install node and yarn"
curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.34.0/install.sh | bash
. ~/.nvm/nvm.sh
nvm install node
npm install yarn -g



echo -e "\n\n\n"
echo "===           DOWNLOAD AND CONFIGURE SPIDHUB REPOSITORY           ==="
echo "======================================================================"
echo ""
echo "=== Clone repository"
git clone https://github.com/pagopa/hub-spid-login-ms.git

echo "= change dir"
cd hub-spid-login-ms
echo "= NEW CURRENT WORKING DIRECTORY: $(pwd)"

echo ""
echo "=== Create SAML certificates"
./scripts/make-certs.sh

echo ""
echo "=== Create JWT key pair"
./scripts/generate-rsa-jwt-key-pair.sh 

echo ""
echo "=== Build well-known JWKS json"
mkdir -p "$HOME/hub-spid-login-ms/well-known/"
( cd $HOME/build-jwks && ./mvnw clean compile exec:java -Dexec.mainClass="buildjwks.BuildJwks"  \
    -Dexec.args="$HOME/hub-spid-login-ms/jwt_rsa_public.pem $HOME/hub-spid-login-ms/well-known/jwks.json" )

echo ""
echo "=== Prepare parameters"

DnsFullDomain=$(cat ../full-dns-name | tr -d '\n')
echo "= DnsFullDomain: ${DnsFullDomain}"

MakecertPrivate=$( cat certs/key.pem | sed -e 's/$/\\n/' | tr -d '\n' | sed -e 's/\\n$//')
echo "= MakecertPrivate: ${MakecertPrivate}"

MakecertPublic=$( cat certs/cert.pem | sed -e 's/$/\\n/' | tr -d '\n' | sed -e 's/\\n$//' )
echo "= MakecertPublic: ${MakecertPublic}"

LoginSuccessDestinationEnpoint=$( cat ../login-success-destination-enpoint | tr -d '\n' )
echo "= LoginSuccessDestinationEnpoint: ${LoginSuccessDestinationEnpoint}"

UserRegistryApiKey=$( cat ../user-registry-api-key | tr -d '\n' )
echo "= UserRegistryApiKey: ${UserRegistryApiKey}"

JwtTokenPrivateKey=$( cat jwt_rsa_key.pem | sed -e 's/$/\\n/' | tr -d '\n' | sed -e 's/\\n$//' )
echo "= JwtTokenPrivateKey: ${JwtTokenPrivateKey}"

echo ""
echo "=== Generate .env and conf-testenv/config.yaml"
export DnsFullDomain MakecertPrivate MakecertPublic LoginSuccessDestinationEnpoint JwtTokenPrivateKey UserRegistryApiKey
echo "\n= .env"
cat ../customized-env | envsubst | tee .env
echo "\n= conf-testenv/config.yaml"
cat ../customized-config.yaml | envsubst | tee conf-testenv/config.yaml

echo "====================================================================="
echo "===                          INSTALL END                          ==="
echo "====================================================================="
