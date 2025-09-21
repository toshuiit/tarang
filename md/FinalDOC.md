# 🚀 Complete AWS Cloud Deployment Guide for Tarang

## 📋 **Overview**
This guide will help you deploy your Tarang simulation platform to AWS cloud with:
- **Flask web app** on EC2 (always-on)
- **EKS clusters** for CPU/GPU job execution (auto-scaling)
- **S3 storage** for user files and results
- **Multi-user support** with complete isolation

## 🔐 **Step 1: AWS Account Setup**

### **1.1 Create AWS Account**
1. Go to [aws.amazon.com](https://aws.amazon.com)
2. Click **"Create AWS Account"**
3. Enter email address and account name
4. Provide payment information (credit card required)
5. Complete phone verification
6. Choose **Basic Support Plan** (free)

### **1.2 Access AWS Console**
1. Go to [console.aws.amazon.com](https://console.aws.amazon.com)
2. Click **"Sign in to the Console"**
3. Enter your **root email** and **password**
4. Complete MFA if enabled

### **1.3 Create IAM User for Tarang Platform**
1. **In AWS Console** → Search for **"IAM"** → Click **IAM**
2. **Left sidebar** → Click **"Users"**
3. Click **"Create user"**
4. **User details**:
   - User name: `tarang-platform`
   - ✅ Check **"Provide user access to the AWS Management Console"**
   - Console password: **Custom password** → Enter: `TarangPlatform2024!`
   - ❌ Uncheck **"Users must create a new password at next sign-in"**
5. Click **"Next"**

### **1.4 Attach Permissions**
1. **Set permissions** → Select **"Attach policies directly"**
2. **Search and select these policies**:
   - ✅ `AmazonS3FullAccess`
   - ✅ `AmazonEKSClusterPolicy`
   - ✅ `AmazonEKSWorkerNodePolicy`
   - ✅ `AmazonEC2FullAccess`
   - ✅ `CloudWatchFullAccess`
   - ✅ `AmazonEC2ContainerRegistryFullAccess`
3. Click **"Next"** → **"Create user"**

### **1.5 Create Access Keys**
1. **Click on the created user** `tarang-platform`
2. Go to **"Security credentials"** tab
3. Scroll to **"Access keys"** → Click **"Create access key"**
4. **Use case** → Select **"Application running on AWS compute service"**
5. Click **"Next"** → **"Create access key"**
6. **IMPORTANT**: Copy and save these credentials:
   ```
   Access Key ID: AKIA1234567890EXAMPLE
   Secret Access Key: wJalrXUtnFEMI/K7MDENG/bPxRfiCYzzzEXAMPLE
   ```
7. Click **"Done"**

## 💻 **Step 2: Local Machine Setup**

### **2.1 Configure AWS CLI**
```bash
# Install AWS CLI (if not already installed)
curl "https://awscli.amazonaws.com/AWSCLIV2.pkg" -o "AWSCLIV2.pkg"
sudo installer -pkg AWSCLIV2.pkg -target /

# Configure with your credentials
aws configure
```

**When prompted, enter:**
```
AWS Access Key ID [None]: AKIA1234567890EXAMPLE
AWS Secret Access Key [None]: wJalrXUtnFEMI/K7MDENG/bPxRfiCYzzzEXAMPLE
Default region name [None]: us-west-2
Default output format [None]: json
```

### **2.2 Test AWS Connection**
```bash
# Verify credentials work
aws sts get-caller-identity

# Should return:
# {
#     "UserId": "AIDACKCEVSQ6C2EXAMPLE",
#     "Account": "123456789012",
#     "Arn": "arn:aws:iam::123456789012:user/tarang-platform"
# }
```

## 🛠️ **Step 3: Application Setup**

### **3.1 Configure Environment**
```bash
cd /Users/toshu/Desktop/tarang1/Tarang-for-demo-main

# Edit .env file with your AWS credentials
nano .env
```

**Update .env file:**
```bash
# AWS Credentials (use the ones you created)
AWS_ACCESS_KEY_ID=AKIA1234567890EXAMPLE
AWS_SECRET_ACCESS_KEY=wJalrXUtnFEMI/K7MDENG/bPxRfiCYzzzEXAMPLE
AWS_DEFAULT_REGION=us-west-2

# S3 Configuration (bucket created automatically)
TARANG_S3_BUCKET=tarang-simulations-prod
TARANG_S3_REGION=us-west-2

# EKS Configuration
TARANG_EKS_CPU_CLUSTER=tarang-cpu-cluster
TARANG_EKS_GPU_CLUSTER=tarang-gpu-cluster

# Other settings (keep as is)
DEFAULT_CPU_REQUEST=2
DEFAULT_MEMORY_REQUEST=4Gi
MAX_CONCURRENT_JOBS_PER_USER=5
```

### **3.2 Install Dependencies**
```bash
# Install AWS integration dependencies
pip install -r aws_requirements.txt
```

## 🚀 **Step 4: AWS Infrastructure Deployment**

### **4.1 Set up S3 and Basic AWS Services**
```bash
# Run AWS setup script
./setup_aws.sh
```

**Expected Output:**
```
✅ AWS CLI already installed
📦 Installing Python dependencies...
✅ AWS credentials configured
🔐 AWS Account: 123456789012
👤 User: arn:aws:iam::123456789012:user/tarang-platform
🪣 Checking S3 bucket: tarang-simulations-prod
📦 Creating S3 bucket: tarang-simulations-prod
✅ S3 bucket created
🎉 AWS setup complete!
```

### **4.2 Create EKS Clusters for Job Execution**
```bash
# Create EKS clusters (takes 40+ minutes)
./setup_eks.sh
```

**Expected Output:**
```
🚀 Setting up Tarang EKS Clusters for Job Execution...
🔍 Checking prerequisites...
✅ AWS CLI already installed
✅ kubectl installed
✅ eksctl installed
🌍 Region: us-west-2
💻 CPU Cluster: tarang-cpu-cluster
🎮 GPU Cluster: tarang-gpu-cluster

🏗️ Creating CPU cluster with auto-scaling (this takes 15-20 minutes)...
📦 Creating cost-optimized CPU cluster...
✅ CPU cluster created successfully

🏗️ Creating GPU cluster with auto-scaling (this takes 15-20 minutes)...
📦 Creating cost-optimized GPU cluster...
✅ GPU cluster created successfully

🎉 EKS setup complete!
💰 Base Cost (idle): ~$171/month
```

### **4.3 Deploy Flask App to EC2**
```bash
# Create EC2 instance for web app
./deploy_ec2.sh
```

**Expected Output:**
```
🚀 Deploying Tarang to EC2...
🔑 Setting up SSH key pair...
📦 Creating SSH key pair...
✅ SSH key created: ~/.ssh/tarang-key.pem
🔒 Setting up security group...
📦 Creating security group...
✅ Security group created: sg-1234567890abcdef0
🚀 Launching EC2 instance...
✅ EC2 instance launched: i-1234567890abcdef0
⏳ Waiting for instance to be running...
✅ Instance is running!
🌐 Public IP: 54.123.45.67

🎉 EC2 setup complete!
📋 Next steps:
1. Wait 2-3 minutes for instance initialization
2. Edit deploy_app.sh and add your AWS credentials
3. Run: ./deploy_app.sh
4. Access your app at: http://54.123.45.67
```

### **4.4 Deploy Application to EC2**
```bash
# Edit deployment script with your credentials
nano deploy_app.sh
```

**Update the AWS credentials section:**
```bash
cat > ~/.aws/credentials << 'AWS_CREDS'
[default]
aws_access_key_id = AKIA1234567890EXAMPLE
aws_secret_access_key = wJalrXUtnFEMI/K7MDENG/bPxRfiCYzzzEXAMPLE
AWS_CREDS
```

**Deploy the application:**
```bash
# Deploy to EC2
./deploy_app.sh
```

**Expected Output:**
```
📦 Deploying application to EC2...
✅ Application deployed successfully!
🌐 Access your app at: http://54.123.45.67
```

## 🧪 **Step 5: Testing Your Deployment**

### **5.1 Access Web Application**
1. **Open browser** → Go to `http://YOUR_EC2_PUBLIC_IP`
2. **Create account** or **login** with existing credentials
3. **Navigate to Jobs** → Click "Jobs" in navigation menu

### **5.2 Test Job Submission**
1. **Configure Simulation**:
   - Go to **"Run Configuration"**
   - Set **Device**: CPU or GPU
   - Configure other parameters
   - Click **"Save Configuration"**

2. **Submit Job**:
   - Go to **"Jobs"** dashboard
   - Click **"Submit Job"**
   - Enter **Job Name**: "Test Simulation"
   - Enter **Description**: "Testing AWS deployment"
   - Click **"Submit Job"**

3. **Monitor Job**:
   - Job should appear in dashboard
   - Status will change: Pending → Queued → Running → Completed
   - EKS nodes will automatically spin up for job execution

### **5.3 Verify AWS Resources**
```bash
# Check S3 bucket
aws s3 ls s3://tarang-simulations-prod/

# Check EKS clusters
kubectl get nodes --context=tarang-cpu-cluster
kubectl get nodes --context=tarang-gpu-cluster

# Check running jobs
kubectl get jobs -A
```

## 📊 **Step 6: User Management**

### **6.1 Application User Accounts**
- **Users register** via web interface
- **No AWS access** needed for users
- **Complete isolation** between users
- **Admin panel** available for user management

### **6.2 AWS Console Access (Admin Only)**
- **Login URL**: [console.aws.amazon.com](https://console.aws.amazon.com)
- **Username**: `tarang-platform`
- **Password**: `TarangPlatform2024!`
- **Use for**: Monitoring costs, managing resources

## 💰 **Step 7: Cost Monitoring**

### **7.1 AWS Cost Dashboard**
1. **AWS Console** → **Billing and Cost Management**
2. **Cost Explorer** → View daily/monthly costs
3. **Budgets** → Set up cost alerts

### **7.2 Expected Monthly Costs**
```
Base Infrastructure (Always Running):
├── EC2 Flask App (t3.medium): $25/month
├── EKS CPU Control Plane: $73/month
├── EKS GPU Control Plane: $73/month
└── Total Base Cost: $171/month

Variable Costs (When Jobs Running):
├── CPU Nodes (t3.medium): $30/month per node
├── GPU Nodes (p3.2xlarge): $918/month per node
└── S3 Storage: ~$1-10/month
```

## 🔧 **Step 8: Maintenance Scripts**

### **8.1 Available Scripts**
- `./setup_aws.sh` - Initial AWS setup and S3 configuration
- `./setup_eks.sh` - Create EKS clusters for job execution
- `./deploy_ec2.sh` - Create EC2 instance for web app
- `./deploy_app.sh` - Deploy application to EC2 (generated by deploy_ec2.sh)

### **8.2 Monitoring Commands**
```bash
# Check application status
ssh -i ~/.ssh/tarang-key.pem ubuntu@YOUR_EC2_IP
sudo systemctl status tarang
sudo systemctl status nginx

# View application logs
sudo journalctl -u tarang -f

# Check EKS cluster status
kubectl get nodes
kubectl get jobs -A
kubectl top nodes
```

## 🚨 **Troubleshooting**

### **Common Issues:**

1. **AWS Credentials Error**:
   ```bash
   aws configure list
   aws sts get-caller-identity
   ```

2. **EKS Connection Issues**:
   ```bash
   aws eks update-kubeconfig --region us-west-2 --name tarang-cpu-cluster
   kubectl config get-contexts
   ```

3. **EC2 Connection Issues**:
   ```bash
   # Check security group allows port 80 and 5000
   aws ec2 describe-security-groups --group-names tarang-sg
   ```

4. **Application Not Starting**:
   ```bash
   ssh -i ~/.ssh/tarang-key.pem ubuntu@YOUR_EC2_IP
   cd /opt/tarang
   source venv/bin/activate
   python app.py  # Run manually to see errors
   ```

## 🎉 **Success Checklist**

- ✅ AWS account created and configured
- ✅ IAM user `tarang-platform` created with proper permissions
- ✅ AWS CLI configured with access keys
- ✅ S3 bucket created automatically
- ✅ EKS clusters created and configured
- ✅ EC2 instance running Flask application
- ✅ Web application accessible via public IP
- ✅ Jobs can be submitted and executed
- ✅ Users can register and use the platform

## 📞 **Support**

If you encounter issues:
1. Check the troubleshooting section above
2. Verify all AWS credentials are correct
3. Ensure all required AWS permissions are attached
4. Check AWS CloudWatch logs for detailed error messages

**Your Tarang simulation platform is now fully deployed on AWS cloud!** 🚀

Users can access it at `http://YOUR_EC2_PUBLIC_IP` and submit CPU/GPU simulation jobs that will automatically execute on your EKS clusters.
