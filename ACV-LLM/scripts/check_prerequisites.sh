sudo -v
docker -v
if [ $? -eq 0 ]; then
    echo "Docker is already installed"
else
    echo "Please install Docker first"
    exit 1
fi

# add user to docker group to ensure minikube can be initialized properly
sudo usermod -aG docker $USER
newgrp docker