#!/bin/bash

# ===================== 颜色定义 =====================
RED='\033[1;31m'    # Bold Red for errors or critical inputs
GREEN='\033[1;32m'  # Bold Green for prompts and success messages
YELLOW='\033[1;33m' # Bold Yellow for input and warnings
BLUE='\033[1;34m'   # Bold Blue for parameter values
NC='\033[0m'        # No color

# ===================== 函数定义（Chaos Mesh安装和卸载） =====================
check_helm_repo() {
    local repo_name=$1
    helm repo list | grep -q "$repo_name"
}

setup_chaos_mesh() {
    echo -e "${GREEN}Starting the installation of Chaos Mesh...${NC}"
    REPO_NAME="chaos-mesh"
    REPO_URL="https://charts.chaos-mesh.org"

    if ! check_helm_repo "$REPO_NAME"; then
        echo -e "${YELLOW}Adding Helm repo: ${BLUE}$REPO_NAME${NC}"
        helm repo add "$REPO_NAME" "$REPO_URL"
        helm repo update
        echo -e "${GREEN}Helm repo added and updated successfully.${NC}"
    else
        echo -e "${BLUE}Helm repo ${REPO_NAME} already exists.${NC}"
    fi

    echo -e "${YELLOW}Checking for 'chaos-mesh' namespace...${NC}"
    if ! kubectl get ns chaos-mesh &>/dev/null; then
        echo -e "${YELLOW}Creating namespace 'chaos-mesh'...${NC}"
        kubectl create ns chaos-mesh
        echo -e "${GREEN}Namespace 'chaos-mesh' created.${NC}"
    else
        echo -e "${BLUE}Namespace 'chaos-mesh' already exists.${NC}"
    fi

    echo -e "${YELLOW}Installing or upgrading Chaos Mesh...${NC}"
    helm upgrade --install "$REPO_NAME" chaos-mesh/"$REPO_NAME" -n chaos-mesh --version 2.6.3
    echo -e "${GREEN}Chaos Mesh installation/upgrade completed.${NC}"
}

uninstall_chaos_mesh() {
    echo -e "${RED}Uninstalling Chaos Mesh...${NC}"
    helm uninstall chaos-mesh -n chaos-mesh
    if [ $? -eq 0 ]; then
        echo -e "${GREEN}Chaos Mesh uninstalled successfully.${NC}"
    else
        echo -e "${RED}Error during Chaos Mesh uninstallation.${NC}"
    fi

    echo -e "${YELLOW}Deleting namespace 'chaos-mesh'...${NC}"
    kubectl delete ns chaos-mesh &>/dev/null
    if [ $? -eq 0 ]; then
        echo -e "${GREEN}Namespace 'chaos-mesh' deleted successfully.${NC}"
    else
        echo -e "${BLUE}Namespace 'chaos-mesh' already deleted or does not exist.${NC}"
    fi
}

# ===================== 函数定义（Chaos 注入） =====================
# 列出chaos注入类型
list_chaos_injection_types() {
    echo -e "${GREEN}Available types of chaos injection:${NC}"
    if [[ -d "src/chaos_inject/chaos_yaml" ]]; then
        local found_file=false
        for file in src/chaos_inject/chaos_yaml/*.yaml; do
            if [[ -e "$file" ]]; then
                found_file=true
                echo -e "- ${BLUE}$(basename "$file" .yaml)${NC}"
            fi
        done
        if [[ $found_file == false ]]; then
            echo -e "${RED}No chaos injection types found.${NC}"
            exit 1
        fi
    else
        echo -e "${RED}Directory src/chaos_inject/chaos_yaml does not exist.${NC}"
        exit 1
    fi
}

# 列出Kubernetes Namespaces
list_kubernetes_namespaces() {
    echo -e "${GREEN}Available Kubernetes namespaces:${NC}"
    namespaces=$(kubectl get namespaces --no-headers -o custom-columns=":metadata.name")
    if [[ -z "$namespaces" ]]; then
        echo -e "${RED}No namespaces found.${NC}"
        exit 1
    fi
    echo "$namespaces" | while read -r ns; do
        echo -e "- ${BLUE}$ns${NC}"
    done
}

# 列出Namespace中的服务
list_services_in_namespace() {
    local namespace=$1
    echo -e "${GREEN}Available services in namespace '${BLUE}$namespace${GREEN}':${NC}"
    services=$(kubectl get services -n "$namespace" --no-headers -o custom-columns=":metadata.name")
    if [[ -z "$services" ]]; then
        echo -e "${RED}No services found in namespace '$namespace'.${NC}"
        exit 1
    fi
    echo "$services" | while read -r svc; do
        echo -e "- ${BLUE}$svc${NC}"
    done
}

inject_chaos() {
    # 列出并选择chaos类型
    list_chaos_injection_types
    echo -e "${GREEN}Please specify the type of chaos injection:${NC}"
    read CHAOS_TYPE

    # 列出并选择namespace
    list_kubernetes_namespaces
    echo -e "${GREEN}Please specify the Kubernetes namespace:${NC}"
    read NAMESPACE

    # 列出并选择service
    list_services_in_namespace "$NAMESPACE"
    echo -e "${GREEN}Please specify the service name:${NC}"
    read SERVICE

    # 显示参数
    echo -e "${GREEN}Injecting chaos with the following parameters:${NC}"
    echo -e "  ${BLUE}Type:${NC} $CHAOS_TYPE"
    echo -e "  ${BLUE}Namespace:${NC} $NAMESPACE"
    echo -e "  ${BLUE}Service:${NC} $SERVICE"

    # 调用 Python 脚本执行注入
    python3 -m src.chaos_inject.main --operation "inject" --namespace "$NAMESPACE" --component "$SERVICE" --chaostype "$CHAOS_TYPE"
}

deprecate_chaos() {
    # 列出并选择chaos类型
    list_chaos_injection_types
    echo -e "${GREEN}Please specify the type of chaos injection to deprecate:${NC}"
    read CHAOS_TYPE

    # 列出并选择namespace
    list_kubernetes_namespaces
    echo -e "${GREEN}Please specify the Kubernetes namespace:${NC}"
    read NAMESPACE

    # 列出并选择service
    list_services_in_namespace "$NAMESPACE"
    echo -e "${GREEN}Please specify the service name to deprecate chaos:${NC}"
    read SERVICE

    # 显示参数
    echo -e "${GREEN}Deprecating chaos injection with the following parameters:${NC}"
    echo -e "  ${BLUE}Type:${NC} $CHAOS_TYPE"
    echo -e "  ${BLUE}Namespace:${NC} $NAMESPACE"
    echo -e "  ${BLUE}Service:${NC} $SERVICE"

    # 调用 Python 脚本撤销注入
    python3 -m src.chaos_inject.main --operation "deprecate" --namespace "$NAMESPACE" --component "$SERVICE" --chaostype "$CHAOS_TYPE"
}

# ===================== 主逻辑入口 =====================
echo -e "${GREEN}Please select an operation:${NC}"
echo -e "${YELLOW}setup-mesh${NC}     - Install or upgrade Chaos Mesh"
echo -e "${YELLOW}uninstall-mesh${NC} - Uninstall Chaos Mesh and delete namespace"
echo -e "${YELLOW}inject${NC}         - Inject chaos into a service"
echo -e "${YELLOW}deprecate${NC}      - Deprecate an existing chaos injection"
read OPERATION

case $OPERATION in
    setup-mesh)
        setup_chaos_mesh
        ;;
    uninstall-mesh)
        uninstall_chaos_mesh
        ;;
    inject)
        inject_chaos
        ;;
    deprecate)
        deprecate_chaos
        ;;
    *)
        echo -e "${RED}Invalid operation selected. Please choose from 'setup-mesh', 'uninstall-mesh', 'inject', or 'deprecate'.${NC}"
        exit 1
        ;;
esac
