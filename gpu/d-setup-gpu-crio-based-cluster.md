# Use ImageVolume feature in 1.31 kubernetes

### 1. Prepare a ubuntu22.04 VM with a GPU
my paras:
a2-highgpu-1g
1 x NVIDIA A100 40GB

### 2. Install cri-o 1.31 and kubernetes 1.31

#### 2.1 preparations for cri-o:
```
cat <<EOF | sudo tee /etc/modules-load.d/k8s.conf
overlay
br_netfilter
EOF

sudo modprobe overlay
sudo modprobe br_netfilter

cat <<EOF | sudo tee /etc/sysctl.d/k8s.conf
net.bridge.bridge-nf-call-iptables  = 1
net.bridge.bridge-nf-call-ip6tables = 1
net.ipv4.ip_forward                 = 1
EOF

sudo sysctl --system

lsmod | grep br_netfilter
lsmod | grep overlay

sysctl net.bridge.bridge-nf-call-iptables net.bridge.bridge-nf-call-ip6tables net.ipv4.ip_forward
```

#### 2.2 install 1.31 cri-0, kubelet, kubeadm, kubectl
```
apt-get update
apt-get install -y software-properties-common curl

curl -fsSL https://pkgs.k8s.io/core:/stable:/v1.31/deb/Release.key |
    gpg --dearmor -o /etc/apt/keyrings/kubernetes-apt-keyring.gpg
echo "deb [signed-by=/etc/apt/keyrings/kubernetes-apt-keyring.gpg] https://pkgs.k8s.io/core:/stable:/v1.31/deb/ /" |
    tee /etc/apt/sources.list.d/kubernetes.list
    

curl -fsSL https://pkgs.k8s.io/addons:/cri-o:/stable:/v1.31/deb/Release.key |
    gpg --dearmor -o /etc/apt/keyrings/cri-o-apt-keyring.gpg
echo "deb [signed-by=/etc/apt/keyrings/cri-o-apt-keyring.gpg] https://pkgs.k8s.io/addons:/cri-o:/stable:/v1.31/deb/ /" |
    tee /etc/apt/sources.list.d/cri-o.list
    
apt-get update
apt-get install -y cri-o kubelet kubeadm kubectl

systemctl start crio.service
```

#### 2.3 prepare a kubeadm.config, enabling ImageVolume feature gate:
```
cat kubeadm.config 
apiVersion: kubeadm.k8s.io/v1beta3
kind: ClusterConfiguration
apiServer:
  extraArgs:
    feature-gates: "ImageVolume=true"
---
apiVersion: kubelet.config.k8s.io/v1beta1
kind: KubeletConfiguration
featureGates:
  ImageVolume: true
```

#### 2.4 Start kubernetes
```
kubeadm init --config=kubeadm.config

mkdir -p $HOME/.kube
sudo cp -i /etc/kubernetes/admin.conf $HOME/.kube/config
sudo chown $(id -u):$(id -g) $HOME/.kube/config
  
kubectl taint nodes --all node-role.kubernetes.io/control-plane-

kubectl get node -owide
NAME       STATUS   ROLES           AGE     VERSION   INTERNAL-IP    EXTERNAL-IP   OS-IMAGE             KERNEL-VERSION   CONTAINER-RUNTIME
demo-gpu   Ready    control-plane   6m59s   v1.31.2   10.240.0.107   <none>        Ubuntu 22.04.5 LTS   6.8.0-1015-gcp   cri-o://1.31.1

kubectl describe pod kube-apiserver-demo-gpu -n kube-system | grep ImageVolume
      --feature-gates=ImageVolume=true
      
cat /var/lib/kubelet/config.yaml  | grep ImageVolume -C 1
featureGates:
  ImageVolume: true
fileCheckFrequency: 0s
```

#### 2.5 create a pod

```
machine: ~# cat image-volumes.yaml 
apiVersion: v1
kind: Pod
metadata:
  name: image-volume
spec:
  containers:
  - name: shell
    command: ["sleep", "infinity"]
    image: debian
    volumeMounts:
    - name: volume
      mountPath: /volume
  volumes:
  - name: volume
    image:
      reference: quay.io/crio/artifact:v1
      pullPolicy: IfNotPresent
      
machine: ~# kubectl  exec -it image-volume -- sh
# apt update && apt install tree
# tree /volume
/volume
|-- dir
|   `-- file
`-- file

2 directories, 2 files
```

Reference:
- https://kubernetes.io/blog/2023/10/10/cri-o-community-package-infrastructure/
- https://sestegra.medium.com/using-oci-volume-source-in-kubernetes-pods-06d62fb72086
- https://kubernetes.io/docs/tasks/configure-pod-container/image-volumes/