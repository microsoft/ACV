# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

: ${MINKUBE_CPUS:=6}
: ${MINIKUBE_MEMORY:=16384}

check_helm_repo() {
    REPO_NAME=$1
    REPO_URL=$2
    if helm repo list | grep -q "^${REPO_NAME}[[:space:]]*${REPO_URL}"; then
        echo "Helm repository '${REPO_NAME}' is already added."
        return 0
    else
        echo "Helm repository '${REPO_NAME}' is not added."
        return 1
    fi
}

init_minikube_environment() {
    # enable minikube addons
    minikube addons enable metrics-server
    # install Locust Kubernetes Operator
    # https://abdelrhmanhamouda.github.io/locust-k8s-operator/helm_deploy/
    echo "installing Locust Kubernetes Operator..."
    REPO_NAME="locust-k8s-operator"
    REPO_URL="https://abdelrhmanhamouda.github.io/locust-k8s-operator/"
    if ! check_helm_repo $REPO_NAME $REPO_URL; then
        helm repo add $REPO_NAME $REPO_URL
        helm install $REPO_NAME locust-k8s-operator/$REPO_NAME
    fi

    # install Chaos Mesh
    # https://chaos-mesh.org/docs/production-installation-using-helm/
    echo "installing Chaos Mesh..."
    REPO_NAME="chaos-mesh"
    REPO_URL="https://charts.chaos-mesh.org"
    if ! check_helm_repo $REPO_NAME $REPO_URL; then
        helm repo add $REPO_NAME $REPO_URL
        kubectl create ns chaos-mesh
        helm install $REPO_NAME chaos-mesh/$REPO_NAME -n=chaos-mesh --version 2.6.3
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
    sudo install -o root -g root -m 0755 kubectl /usr/local/bin/kubectl && rm kubectl
fi

# install helm
# https://v3.helm.sh/docs/intro/install/
helm version
if [ $? -eq 0 ]; then
    echo "helm is already installed"
else
    echo "installing helm..."
    curl -fsSL -o get_helm.sh https://raw.githubusercontent.com/helm/helm/main/scripts/get-helm-3
    chmod 700 get_helm.sh && ./get_helm.sh && rm get_helm.sh
fi

minikube_status=$(minikube status --format='{{.Host}}')
if [ "$minikube_status" == "Running" ]; then
    echo "minikube is already running"
    while true; do
        read -p "Do you want to rebuild minikube? [y/n] " yn
        case $yn in
            [Yy]* ) minikube delete --all && minikube start --cpus=$MINKUBE_CPUS --memory=$MINIKUBE_MEMORY; break;;
            [Nn]* ) break;;
            * ) echo "Please answer yes or no.";;
        esac
    done
else
    minikube start --cpus=$MINKUBE_CPUS --memory=$MINIKUBE_MEMORY
fi

init_minikube_environment