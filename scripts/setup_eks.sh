#!/bin/bash

# 🚀 Tarang EKS Setup Script

echo "🚀 Setting up Tarang EKS Clusters for Job Execution..."

# Check prerequisites
echo "🔍 Checking prerequisites..."

# Check AWS CLI
if ! command -v aws &> /dev/null; then
    echo "❌ AWS CLI not found. Please run ./setup_aws.sh first"
    exit 1
fi

# Check AWS credentials
if ! aws sts get-caller-identity &> /dev/null; then
    echo "❌ AWS credentials not configured. Please run ./setup_aws.sh first"
    exit 1
fi

# Check kubectl
if ! command -v kubectl &> /dev/null; then
    echo "📦 Installing kubectl..."
    curl -LO "https://dl.k8s.io/release/$(curl -L -s https://dl.k8s.io/release/stable.txt)/bin/darwin/amd64/kubectl"
    chmod +x kubectl
    sudo mv kubectl /usr/local/bin/
    echo "✅ kubectl installed"
fi

# Check eksctl
if ! command -v eksctl &> /dev/null; then
    echo "📦 Installing eksctl..."
    if command -v brew &> /dev/null; then
        brew tap weaveworks/tap
        brew install weaveworks/tap/eksctl
    else
        curl --silent --location "https://github.com/weaveworks/eksctl/releases/latest/download/eksctl_$(uname -s)_amd64.tar.gz" | tar xz -C /tmp
        sudo mv /tmp/eksctl /usr/local/bin
    fi
    echo "✅ eksctl installed"
fi

# Get configuration
REGION=$(grep AWS_DEFAULT_REGION .env | cut -d'=' -f2 || echo "us-west-2")
CPU_CLUSTER=$(grep TARANG_EKS_CPU_CLUSTER .env | cut -d'=' -f2 || echo "tarang-cpu-cluster")
GPU_CLUSTER=$(grep TARANG_EKS_GPU_CLUSTER .env | cut -d'=' -f2 || echo "tarang-gpu-cluster")

echo "🌍 Region: $REGION"
echo "💻 CPU Cluster: $CPU_CLUSTER"
echo "🎮 GPU Cluster: $GPU_CLUSTER"

# Create CPU cluster (cost-optimized)
echo ""
echo "🏗️  Creating CPU cluster with auto-scaling (this takes 15-20 minutes)..."
if eksctl get cluster --name $CPU_CLUSTER --region $REGION &> /dev/null; then
    echo "✅ CPU cluster $CPU_CLUSTER already exists"
else
    echo "📦 Creating cost-optimized CPU cluster..."
    eksctl create cluster \
        --name $CPU_CLUSTER \
        --region $REGION \
        --nodegroup-name cpu-workers \
        --node-type t3.medium \
        --nodes 0 \
        --nodes-min 0 \
        --nodes-max 20 \
        --managed \
        --with-oidc \
        --asg-access \
        --node-labels="workload-type=cpu"
    
    if [ $? -eq 0 ]; then
        echo "✅ CPU cluster created successfully"
    else
        echo "❌ Failed to create CPU cluster"
        exit 1
    fi
fi

# Create GPU cluster (cost-optimized)
echo ""
echo "🏗️  Creating GPU cluster with auto-scaling (this takes 15-20 minutes)..."
if eksctl get cluster --name $GPU_CLUSTER --region $REGION &> /dev/null; then
    echo "✅ GPU cluster $GPU_CLUSTER already exists"
else
    echo "📦 Creating cost-optimized GPU cluster..."
    eksctl create cluster \
        --name $GPU_CLUSTER \
        --region $REGION \
        --nodegroup-name gpu-workers \
        --node-type p3.2xlarge \
        --nodes 0 \
        --nodes-min 0 \
        --nodes-max 10 \
        --managed \
        --with-oidc \
        --asg-access \
        --node-labels="workload-type=gpu"
    
    if [ $? -eq 0 ]; then
        echo "✅ GPU cluster created successfully"
    else
        echo "❌ Failed to create GPU cluster"
        exit 1
    fi
fi

# Update kubeconfig
echo ""
echo "🔧 Updating kubeconfig..."
aws eks update-kubeconfig --region $REGION --name $CPU_CLUSTER
aws eks update-kubeconfig --region $REGION --name $GPU_CLUSTER

# Install NVIDIA device plugin for GPU cluster
echo ""
echo "🎮 Setting up GPU support..."
kubectl config use-context $(kubectl config get-contexts -o name | grep $GPU_CLUSTER)
kubectl apply -f https://raw.githubusercontent.com/NVIDIA/k8s-device-plugin/v0.14.1/nvidia-device-plugin.yml

# Create namespaces and RBAC
echo ""
echo "🔐 Setting up Kubernetes RBAC..."

# Create service account and cluster role
cat <<EOF | kubectl apply -f -
apiVersion: v1
kind: ServiceAccount
metadata:
  name: tarang-job-runner
  namespace: kube-system
---
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRole
metadata:
  name: tarang-job-manager
rules:
- apiGroups: [""]
  resources: ["namespaces"]
  verbs: ["get", "list", "create", "delete"]
- apiGroups: [""]
  resources: ["resourcequotas"]
  verbs: ["get", "list", "create", "update", "delete"]
- apiGroups: ["batch"]
  resources: ["jobs"]
  verbs: ["get", "list", "watch", "create", "update", "patch", "delete"]
- apiGroups: [""]
  resources: ["pods"]
  verbs: ["get", "list", "watch"]
- apiGroups: [""]
  resources: ["pods/log"]
  verbs: ["get", "list"]
---
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRoleBinding
metadata:
  name: tarang-job-manager-binding
subjects:
- kind: ServiceAccount
  name: tarang-job-runner
  namespace: kube-system
roleRef:
  kind: ClusterRole
  name: tarang-job-manager
  apiGroup: rbac.authorization.k8s.io
EOF

# Apply to both clusters
kubectl config use-context $(kubectl config get-contexts -o name | grep $CPU_CLUSTER)
kubectl apply -f - <<EOF
apiVersion: v1
kind: ServiceAccount
metadata:
  name: tarang-job-runner
  namespace: kube-system
EOF

# Install cluster autoscaler
echo ""
echo "📈 Installing cluster autoscaler..."
curl -o cluster-autoscaler-autodiscover.yaml https://raw.githubusercontent.com/kubernetes/autoscaler/master/cluster-autoscaler/cloudprovider/aws/examples/cluster-autoscaler-autodiscover.yaml

# Update cluster name in autoscaler config
sed -i.bak "s/<YOUR CLUSTER NAME>/$CPU_CLUSTER/g" cluster-autoscaler-autodiscover.yaml
kubectl apply -f cluster-autoscaler-autodiscover.yaml
rm cluster-autoscaler-autodiscover.yaml*

# Test clusters
echo ""
echo "🧪 Testing clusters..."
echo "CPU Cluster nodes:"
kubectl config use-context $(kubectl config get-contexts -o name | grep $CPU_CLUSTER)
kubectl get nodes

echo ""
echo "GPU Cluster nodes:"
kubectl config use-context $(kubectl config get-contexts -o name | grep $GPU_CLUSTER)
kubectl get nodes

# Update .env file with cluster info
echo ""
echo "📝 Updating configuration..."
if ! grep -q "TARANG_EKS_CPU_CLUSTER" .env; then
    echo "TARANG_EKS_CPU_CLUSTER=$CPU_CLUSTER" >> .env
fi
if ! grep -q "TARANG_EKS_GPU_CLUSTER" .env; then
    echo "TARANG_EKS_GPU_CLUSTER=$GPU_CLUSTER" >> .env
fi

echo ""
echo "🎉 EKS setup complete!"
echo ""
echo "📊 Cluster Summary:"
echo "💻 CPU Cluster: $CPU_CLUSTER (t3.medium nodes)"
echo "🎮 GPU Cluster: $GPU_CLUSTER (p3.2xlarge nodes)"
echo "🌍 Region: $REGION"
echo ""
echo "💰 Estimated Monthly Cost (Full Cloud):"
echo "🖥️  EC2 Flask App: ~$25/month (t3.medium)"
echo "💻 CPU Cluster Control Plane: $73/month"
echo "🎮 GPU Cluster Control Plane: $73/month"
echo "⚡ CPU Nodes (when running): $30/month per node"
echo "🚀 GPU Nodes (when running): $918/month per node"
echo "📊 Base Cost (idle): ~$171/month"
echo "📈 With Jobs Running: ~$200-2000/month"
echo ""
echo "🚀 You can now run jobs on EKS!"
echo "🌐 Start your app: python app.py"
echo "📱 Go to: http://localhost:5000/jobs/dashboard"
