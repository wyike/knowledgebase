# Setup GPU in GKE


refer:
- https://docs.nvidia.com/datacenter/cloud-native/gpu-operator/latest/google-gke.html
- https://docs.nvidia.com/ai-enterprise/deployment/cloud/latest/google-gke.html
- https://enterprise-support.nvidia.com/s/article/GPU-Operator-Installation-Failed-Clean-Uninstallation-process-Auto-and-Manual

### 1. create gke cluster
create a gke cluster with A100 GPU attached to the worker node
```
gcloud beta container clusters create demo1-cluster \
    --project <project-id> \
    --location us-central1-a \
    --release-channel "regular" \
    --machine-type "a2-highgpu-1g" \
    --accelerator "type=nvidia-tesla-a100,count=1" \
    --image-type "UBUNTU_CONTAINERD" \
    --node-labels="gke-no-default-nvidia-gpu-device-plugin=true" \
    --disk-type "pd-standard" \
    --disk-size "1000" \
    --no-enable-intra-node-visibility \
    --metadata disable-legacy-endpoints=true \
    --num-nodes "1" \
    --logging=SYSTEM,WORKLOAD \
    --monitoring=SYSTEM \
    --enable-ip-alias \
    --no-enable-master-authorized-networks \
    --tags=nvidia-ingress-all \
    --no-enable-ip-alias \
    --cluster-version 1.31.1-gke.1678000
```

### 2. create resourcequota in gpu-operator namespace in this cluster

This is very important and the prerequisite to install gpu-operator afterwards in gke.

gpu-operator-quota.yaml:
```
apiVersion: v1
kind: ResourceQuota
metadata:
  name: gpu-operator-quota
spec:
  hard:
    pods: 100
  scopeSelector:
    matchExpressions:
    - operator: In
      scopeName: PriorityClass
      values:
        - system-node-critical
        - system-cluster-critical
```

kubectl apply -n gpu-operator -f gpu-operator-quota.yaml

### 3. install gpu operator

```
apt-get update && curl -fsSL https://raw.githubusercontent.com/helm/helm/main/scripts/get-helm-3 | bash

helm repo add nvidia https://helm.ngc.nvidia.com/nvidia \
    && helm repo update
helm install --wait --generate-name \
 -n gpu-operator --create-namespace \
 nvidia/gpu-operator --debug
```
Waiting for all related operator components running and NVIDIA drivers will be installed to each workers.

### 4. Run your gpu consuming applications

