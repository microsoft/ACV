# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

kubectl apply -f kubernetes/sock-shop-backup
echo "--------Waiting for cluster to be stable--------"
sleep 30