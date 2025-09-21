# 🚀 AWS Cloud Setup for Tarang

## 📋 **Quick Setup (10 minutes)**

### **Step 1: Get AWS Credentials**
1. **AWS Console** → **IAM** → **Create User**: `tarang-platform`
2. **Attach policies**: 
   - `AmazonS3FullAccess` (for file storage)
   - `AmazonEKSClusterPolicy` (for job execution)
   - `AmazonEKSWorkerNodePolicy` (for job execution)
   - `AmazonEC2FullAccess` (for EKS nodes)
   - `CloudWatchFullAccess` (for monitoring)
3. **Create access key** → Save credentials

### **Step 2: Configure & Run**
```bash
# Configure AWS
aws configure
# Enter: Access Key, Secret Key, region: us-west-2, format: json

# Run setup
./setup_aws.sh

# Start app
python app.py
```

### **Step 3: Test**
1. Go to `http://localhost:5000/jobs/dashboard`
2. Submit a job → para.py uploads to S3 automatically

## 🎯 **What You Get**
- ✅ S3 file storage (automatic bucket creation)
- ✅ Multi-user job management
- ✅ CPU/GPU job routing
- ✅ Real-time job status tracking

## 🚀 **For Full EKS Job Execution**
```bash
# Set up EKS clusters for running actual jobs (takes 40+ minutes)
./setup_eks.sh
```

## 💰 **Cost Breakdown**
- **S3 only**: ~$1/month (file storage)
- **S3 + EKS**: ~$850-4000/month (CPU + GPU clusters)
  - CPU cluster: ~$150-500/month (t3.medium nodes)
  - GPU cluster: ~$700-3500/month (p3.2xlarge nodes)

## 📋 **Setup Phases**
1. **Phase 1**: S3 integration (10 minutes) - Job tracking + file storage
2. **Phase 2**: EKS clusters (40+ minutes) - Actual job execution on cloud
