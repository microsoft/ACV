# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

init_minikube_environment() {
    # enable minikube addons
    minikube addons enable metrics-server
    # install Locust Kubernetes Operator
    # https://abdelrhmanhamouda.github.io/locust-k8s-operator/helm_deploy/
    echo "installing Locust Kubernetes Operator..."
    output=$(helm repo list | grep locust-k8s-operator | wc -l)
    if [ "$output" -ge 0 ]; then
        echo "locust-k8s-operator is already installed"
    else
        helm repo add locust-k8s-operator https://abdelrhmanhamouda.github.io/locust-k8s-operator/
        helm install locust-operator locust-k8s-operator/locust-k8s-operator
    fi

    # install Chaos Mesh
    # https://chaos-mesh.org/docs/production-installation-using-helm/
    echo "installing Chaos Mesh..."
    output=$(helm repo list | grep chaos-mesh | wc -l)
    if [ "$output" -ge 0 ]; then
        echo "chaos-mesh is already installed"
    else
        helm repo add chaos-mesh https://charts.chaos-mesh.org
        kubectl create ns chaos-mesh
        helm install chaos-mesh chaos-mesh/chaos-mesh -n=chaos-mesh --version 2.6.3
    fi

    # install Grafana and Prometheus from local file
    if ! kubectl get ns monitoring >/dev/null 2>&1; then
        echo "installing monitoring components..."
        kubectl apply -f kubernetes/monitoring
    else
        echo "monitoring components is already installed"
    fi
}

# get root access first
sudo -v

# install minikube
# https://minikube.sigs.k8s.io/docs/start/
minikube version
if [ $? -eq 0 ]; then
    echo "minikube is already installed"
else
    echo "installing minikube..."
    curl -LO https://storage.googleapis.com/minikube/releases/latest/minikube-linux-amd64
    sudo install minikube-linux-amd64 /usr/local/bin/minikube && rm minikube-linux-amd64
fi

# install kubectl
# https://kubernetes.io/docs/tasks/tools/install-kubectl-linux/
kubectl version
if [ $? -eq 0 ]; then
    echo "kubectl is already installed"
else
    echo "installing kubectl..."
    curl -LO "https://dl.k8s.io/release/$(curl -L -s https://dl.k8s.io/release/stable.txt)/bin/linux/amd64/kubectl"
    sudo install -o root -g root -m 0755 kubectl /usr/local/bin/kubectl
fi

# install helm
# https://v3.helm.sh/docs/intro/install/
helm version
if [ $? -eq 0 ]; then
    echo "helm is already installed"
else
    echo "installing helm..."
    curl -fsSL -o get_helm.sh https://raw.githubusercontent.com/helm/helm/main/scripts/get-helm-3
    chmod 700 get_helm.sh && ./get_helm.sh
fi

# install RabbitMQ
# https://www.rabbitmq.com/docs/download#downloads-on-github
sudo rabbitmqctl version
if [ $? -eq 0 ]; then
    echo "RabbitMQ is already installed"
else
    echo "installing RabbitMQ..."
    curl -fsSL https://github.com/rabbitmq/rabbitmq-server/releases/download/v3.13.6/rabbitmq-server_3.13.6-1_all.deb | sudo dpkg -i
fi

minikube_status=$(minikube status --format='{{.Host}}')
if [ "$minikube_status" == "Running" ]; then
    echo "minikube is already running"
    while true; do
        read -p "Do you want to rebuild minikube? [y/n] " yn
        case $yn in
            [Yy]* ) minikube delete --all && minikube start --cpus=6 --memory=16384; break;;
            [Nn]* ) break;;
            * ) echo "Please answer yes or no.";;
        esac
    done
else
    minikube start --cpus=6 --memory=16384
fi

init_minikube_environment