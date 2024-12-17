<h1 align="center">
    <b>AutoKube: Simplify Your Microservice Management in Kubernetes</b>
</h1>


<div align="center">

![Python Version](https://img.shields.io/badge/Python-3776AB?&logo=python&logoColor=white-blue&label=3.9%20%7C%203.10%20%7C%203.11)&ensp;
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)&ensp;

</div>

<div align="center">
    <img src="assets/AutoKube.png" width="100">
</div>

**AutoKube** aims to simplify the management of microservices in Kubernetes by leveraging a Large Language Model (LLM)-powered agent management system. AutoKube is designed to streamline both development and operations phases of the DevOps lifecycle, aligning with the respective roles of developers (**Dev**) and operators (**Ops**).
* [**Dev**] Development of Agent-based Management System: AutoKube facilitates setting up an agent-based management system for microservices. This helps developers quickly establish self-managing systems powered by LLM-based agents. See the [Dev](#dev) section for more details.
* [**Ops**] Operations with the Agent-based Management System: AutoKube provides an intuitive tool for microservice operators to manage services, even with limited familiarity, using LLM-based agents. See the [Ops](#ops) section for more details.

This project is a work in progress, and contributions from the community are highly encouraged! Watch this [6-min introduction video](https://youtu.be/IFFLb5mgzY0) to learn more.

AutoKube is inspired by research on applying LLM-based agents for microservice self-management. For more details, see [paper_artifact_arXiv_2407_14402](../paper_artifact_arXiv_2407_14402/README.md) for more details. 


## Dev: Setting up AutoKube for Your Microservice
This section guides developers through setting up AutoKube for a microservice.
### Setup Minikube
Run the following script to set up a Minikube cluster. Follow the on-screen instructions during execution:
```bash
sh scripts/dev/minikube.sh
```

### Setup Prometheus Deployment
Run the following script to deploy Prometheus and forward its port for metrics monitoring. Port forwarding is integrated into the script:
```bash
sh scripts/dev/prometheus.sh
```

### Setup Services
You can deploy example services using the script below. For custom services, refer to the code in src/exp_setup.

```bash
sh scripts/dev/service.sh
```
### (Optional) Setup Chaos-mesh
To enable chaos injection, we provide a setup script that allows you to easily test various potential failure scenarios.

```bash
sh scripts/dev/chaos-mesh.sh 
```

### (Optional) Switch Cluster.
You can swith to other clusters as you want.
```bash
kubectl config get-contexts
kubectl config use-context <context-name>
```


## Ops: Using AutoKube for Your Microservice
For Ops, we provide an easy-to-use command-line tool, AutoKube. By following the instructions below, you can simplify the management of your microservices.
```bash
./AutoKube
```
