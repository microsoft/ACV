<h1 align="center">
    <b>Autokube</b>
</h1>


<div align="center">

![Python Version](https://img.shields.io/badge/Python-3776AB?&logo=python&logoColor=white-blue&label=3.9%20%7C%203.10%20%7C%203.11)&ensp;
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)&ensp;

</div>

<div align="center">
    <img src="assets/AutoKube.png" width="100">
</div>

**AutoKube** provides an automated framework for deploying, managing, and experimenting with microservice-based systems on Kubernetes clusters.


## Roles
For Developers, refer to the [Dev](#dev) section. For Users, refer to the [Ops](#ops) section.

## Dev
### Setup Minikube
First, run the bash script to set up a Minikube cluster. Follow the instructions displayed in the terminal.
```bash
sh scripts/dev/minikube.sh
```

### Setup Prometheus Deployment
Next, run the bash script to set up the Prometheus deployment. Additionally, forward the Prometheus port to enable metric checking, which is also intregated in the bash file.

```bash
sh scripts/dev/prometheus.sh
```

### (Optional) Setup Services
Finally, you can setup the services by applying the bash script, to apply your own services, you can reference the code in src/exp_setup.

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


## Ops
For Ops, we provide an easy-to-use command-line tool, AutoKube. By following the instructions below, you can simplify the management of your microservices.
```bash
./AutoKube
```
