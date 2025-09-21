#!/bin/bash

# 🚀 Tarang AWS Setup Script

echo "🚀 Setting up Tarang AWS Integration..."

# Check if AWS CLI is installed
if ! command -v aws &> /dev/null; then
    echo "❌ AWS CLI not found. Installing..."
    curl "https://awscli.amazonaws.com/AWSCLIV2.pkg" -o "AWSCLIV2.pkg"
    sudo installer -pkg AWSCLIV2.pkg -target /
    rm AWSCLIV2.pkg
    echo "✅ AWS CLI installed"
else
    echo "✅ AWS CLI already installed"
fi

# Install Python dependencies
echo "📦 Installing Python dependencies..."
pip install -r aws_requirements.txt

# Check if AWS is configured
if aws sts get-caller-identity &> /dev/null; then
    echo "✅ AWS credentials configured"
    
    # Get AWS account info
    ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
    USER_ARN=$(aws sts get-caller-identity --query Arn --output text)
    echo "🔐 AWS Account: $ACCOUNT_ID"
    echo "👤 User: $USER_ARN"
    
    # Create S3 bucket if it doesn't exist
    BUCKET_NAME=$(grep TARANG_S3_BUCKET .env | cut -d'=' -f2)
    if [ ! -z "$BUCKET_NAME" ]; then
        echo "🪣 Checking S3 bucket: $BUCKET_NAME"
        if aws s3 ls "s3://$BUCKET_NAME" 2>&1 | grep -q 'NoSuchBucket'; then
            echo "📦 Creating S3 bucket: $BUCKET_NAME"
            aws s3 mb "s3://$BUCKET_NAME" --region us-west-2
            echo "✅ S3 bucket created"
        else
            echo "✅ S3 bucket already exists"
        fi
    fi
    
    echo ""
    echo "🎉 AWS setup complete!"
    echo "🚀 You can now run: python app.py"
    echo "🌐 Then go to: http://localhost:5000/jobs/dashboard"
    
else
    echo "❌ AWS credentials not configured"
    echo ""
    echo "📋 Setup Options:"
    echo ""
    echo "🔐 Option 1 (Recommended): IAM User without MFA"
    echo "1. AWS Console → IAM → Create User: 'tarang-platform'"
    echo "2. Programmatic access only (no console)"
    echo "3. Attach policy: AmazonS3FullAccess"
    echo "4. Get Access Keys → Use below"
    echo ""
    echo "🔑 Option 2: MFA Session (if using MFA everywhere)"
    echo "1. Run: aws configure --profile mfa-user"
    echo "2. Then: aws sts assume-role --role-arn YOUR_ROLE --serial-number YOUR_MFA_DEVICE --token-code 123456"
    echo ""
    echo "💡 Then configure:"
    echo "aws configure"
    echo "Enter your Access Key ID and Secret Access Key"
    echo "Region: us-west-2, Format: json"
fi
