#!/bin/bash

# 🚀 Deploy Tarang Flask App to EC2

echo "🚀 Deploying Tarang to EC2..."

# Configuration
INSTANCE_TYPE="t3.medium"
KEY_NAME="tarang-key"
SECURITY_GROUP="tarang-sg"
REGION=$(grep AWS_DEFAULT_REGION .env | cut -d'=' -f2 || echo "us-west-2")

echo "🌍 Region: $REGION"
echo "💻 Instance Type: $INSTANCE_TYPE"

# Create key pair if it doesn't exist
echo ""
echo "🔑 Setting up SSH key pair..."
if ! aws ec2 describe-key-pairs --key-names $KEY_NAME --region $REGION &> /dev/null; then
    echo "📦 Creating SSH key pair..."
    aws ec2 create-key-pair \
        --key-name $KEY_NAME \
        --region $REGION \
        --query 'KeyMaterial' \
        --output text > ~/.ssh/${KEY_NAME}.pem
    chmod 400 ~/.ssh/${KEY_NAME}.pem
    echo "✅ SSH key created: ~/.ssh/${KEY_NAME}.pem"
else
    echo "✅ SSH key pair already exists"
fi

# Create security group
echo ""
echo "🔒 Setting up security group..."
if ! aws ec2 describe-security-groups --group-names $SECURITY_GROUP --region $REGION &> /dev/null; then
    echo "📦 Creating security group..."
    SECURITY_GROUP_ID=$(aws ec2 create-security-group \
        --group-name $SECURITY_GROUP \
        --description "Tarang Flask App Security Group" \
        --region $REGION \
        --query 'GroupId' \
        --output text)
    
    # Allow SSH (port 22)
    aws ec2 authorize-security-group-ingress \
        --group-id $SECURITY_GROUP_ID \
        --protocol tcp \
        --port 22 \
        --cidr 0.0.0.0/0 \
        --region $REGION
    
    # Allow HTTP (port 80)
    aws ec2 authorize-security-group-ingress \
        --group-id $SECURITY_GROUP_ID \
        --protocol tcp \
        --port 80 \
        --cidr 0.0.0.0/0 \
        --region $REGION
    
    # Allow Flask app (port 5000)
    aws ec2 authorize-security-group-ingress \
        --group-id $SECURITY_GROUP_ID \
        --protocol tcp \
        --port 5000 \
        --cidr 0.0.0.0/0 \
        --region $REGION
    
    echo "✅ Security group created: $SECURITY_GROUP_ID"
else
    echo "✅ Security group already exists"
    SECURITY_GROUP_ID=$(aws ec2 describe-security-groups \
        --group-names $SECURITY_GROUP \
        --region $REGION \
        --query 'SecurityGroups[0].GroupId' \
        --output text)
fi

# Get latest Ubuntu AMI
echo ""
echo "🔍 Finding latest Ubuntu AMI..."
AMI_ID=$(aws ec2 describe-images \
    --owners 099720109477 \
    --filters "Name=name,Values=ubuntu/images/hvm-ssd/ubuntu-jammy-22.04-amd64-server-*" \
    --query 'Images | sort_by(@, &CreationDate) | [-1].ImageId' \
    --output text \
    --region $REGION)

echo "📦 Using AMI: $AMI_ID"

# Create user data script
cat > /tmp/user-data.sh << 'EOF'
#!/bin/bash

# Update system
apt-get update
apt-get upgrade -y

# Install Python and dependencies
apt-get install -y python3 python3-pip python3-venv git nginx

# Install AWS CLI
curl "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o "awscliv2.zip"
unzip awscliv2.zip
./aws/install

# Install kubectl
curl -LO "https://dl.k8s.io/release/$(curl -L -s https://dl.k8s.io/release/stable.txt)/bin/linux/amd64/kubectl"
chmod +x kubectl
mv kubectl /usr/local/bin/

# Install eksctl
curl --silent --location "https://github.com/weaveworks/eksctl/releases/latest/download/eksctl_$(uname -s)_amd64.tar.gz" | tar xz -C /tmp
mv /tmp/eksctl /usr/local/bin

# Create app directory
mkdir -p /opt/tarang
cd /opt/tarang

# Create systemd service
cat > /etc/systemd/system/tarang.service << 'EOL'
[Unit]
Description=Tarang Flask Application
After=network.target

[Service]
Type=simple
User=ubuntu
WorkingDirectory=/opt/tarang
Environment=PATH=/opt/tarang/venv/bin
ExecStart=/opt/tarang/venv/bin/python app.py
Restart=always

[Install]
WantedBy=multi-user.target
EOL

# Configure nginx
cat > /etc/nginx/sites-available/tarang << 'EOL'
server {
    listen 80;
    server_name _;

    location / {
        proxy_pass http://127.0.0.1:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
EOL

ln -s /etc/nginx/sites-available/tarang /etc/nginx/sites-enabled/
rm /etc/nginx/sites-enabled/default

# Enable services
systemctl enable nginx
systemctl enable tarang

echo "✅ EC2 instance setup complete"
EOF

# Launch EC2 instance
echo ""
echo "🚀 Launching EC2 instance..."
INSTANCE_ID=$(aws ec2 run-instances \
    --image-id $AMI_ID \
    --count 1 \
    --instance-type $INSTANCE_TYPE \
    --key-name $KEY_NAME \
    --security-groups $SECURITY_GROUP \
    --user-data file:///tmp/user-data.sh \
    --region $REGION \
    --tag-specifications 'ResourceType=instance,Tags=[{Key=Name,Value=Tarang-Flask-App}]' \
    --query 'Instances[0].InstanceId' \
    --output text)

echo "✅ EC2 instance launched: $INSTANCE_ID"

# Wait for instance to be running
echo ""
echo "⏳ Waiting for instance to be running..."
aws ec2 wait instance-running --instance-ids $INSTANCE_ID --region $REGION

# Get public IP
PUBLIC_IP=$(aws ec2 describe-instances \
    --instance-ids $INSTANCE_ID \
    --region $REGION \
    --query 'Reservations[0].Instances[0].PublicIpAddress' \
    --output text)

echo "✅ Instance is running!"
echo "🌐 Public IP: $PUBLIC_IP"

# Create deployment script
cat > deploy_app.sh << EOF
#!/bin/bash

# Deploy application to EC2
echo "📦 Deploying application to EC2..."

# Copy application files
rsync -avz --exclude='.git' --exclude='__pycache__' --exclude='venv' --exclude='user_data' \
    ./ ubuntu@$PUBLIC_IP:/opt/tarang/

# SSH and setup
ssh -i ~/.ssh/${KEY_NAME}.pem ubuntu@$PUBLIC_IP << 'REMOTE_EOF'
cd /opt/tarang

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r web_requirements.txt
pip install -r aws_requirements.txt

# Set up environment
sudo chown -R ubuntu:ubuntu /opt/tarang

# Configure AWS credentials (you'll need to add these)
mkdir -p ~/.aws
cat > ~/.aws/credentials << 'AWS_CREDS'
[default]
aws_access_key_id = YOUR_ACCESS_KEY_HERE
aws_secret_access_key = YOUR_SECRET_KEY_HERE
AWS_CREDS

cat > ~/.aws/config << 'AWS_CONFIG'
[default]
region = $REGION
output = json
AWS_CONFIG

# Update kubeconfig for EKS
aws eks update-kubeconfig --region $REGION --name tarang-cpu-cluster
aws eks update-kubeconfig --region $REGION --name tarang-gpu-cluster

# Start services
sudo systemctl start tarang
sudo systemctl start nginx

# Check status
sudo systemctl status tarang
sudo systemctl status nginx

echo "✅ Application deployed successfully!"
echo "🌐 Access your app at: http://$PUBLIC_IP"
REMOTE_EOF
EOF

chmod +x deploy_app.sh

echo ""
echo "🎉 EC2 setup complete!"
echo ""
echo "📋 Next steps:"
echo "1. Wait 2-3 minutes for instance initialization"
echo "2. Edit deploy_app.sh and add your AWS credentials"
echo "3. Run: ./deploy_app.sh"
echo "4. Access your app at: http://$PUBLIC_IP"
echo ""
echo "🔑 SSH access: ssh -i ~/.ssh/${KEY_NAME}.pem ubuntu@$PUBLIC_IP"
echo "📊 Instance ID: $INSTANCE_ID"
echo "🌐 Public IP: $PUBLIC_IP"

# Clean up
rm /tmp/user-data.sh
