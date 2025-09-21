# 🔐 AWS MFA Setup Guide for Tarang

## 🎯 **Best Approach: Service User Without MFA**

Since your main AWS account has MFA enabled, create a dedicated service user for the application:

### **Step 1: Create Service User (via AWS Console with MFA)**
1. **Login to AWS Console** (with your MFA as usual)
2. **IAM** → **Users** → **Create User**
3. **Details**:
   - User name: `tarang-platform`
   - Access type: ✅ **Programmatic access** only
   - AWS Console access: ❌ **No** (not needed)
4. **Permissions** (for full EKS support):
   - `AmazonS3FullAccess`
   - `AmazonEKSClusterPolicy`
   - `AmazonEKSWorkerNodePolicy`
   - `AmazonEKSServicePolicy`
   - `AmazonEC2ContainerRegistryFullAccess`
   - `CloudWatchFullAccess`
   - `AmazonEC2FullAccess` (for EKS node management)
5. **MFA**: ❌ **Skip** (not required for service users)
6. **Create User** → **Download Access Keys**

### **Step 2: Configure Application**
```bash
# Use the service user credentials
aws configure

# Enter the tarang-platform credentials:
AWS Access Key ID: AKIA... (from service user)
AWS Secret Access Key: xyz... (from service user)
Default region: us-west-2
Default output format: json
```

### **Step 3: Test**
```bash
# This should work without MFA prompts
aws sts get-caller-identity

# Should return:
# "Arn": "arn:aws:iam::123456789012:user/tarang-platform"
```

## 🔑 **Alternative: MFA Session Tokens**

If you prefer to use MFA everywhere:

### **Option A: Temporary Session**
```bash
# Get temporary credentials (valid for 12 hours)
aws sts get-session-token \
  --serial-number arn:aws:iam::123456789012:mfa/your-username \
  --token-code 123456 \
  --duration-seconds 43200

# Use the temporary credentials in .env file
```

### **Option B: Assume Role with MFA**
```bash
# Create a role that requires MFA
aws sts assume-role \
  --role-arn arn:aws:iam::123456789012:role/TarangServiceRole \
  --role-session-name tarang-session \
  --serial-number arn:aws:iam::123456789012:mfa/your-username \
  --token-code 123456
```

## 💡 **Recommendation**

**Use Option 1 (Service User)** because:
- ✅ **Simple**: No MFA prompts during development
- ✅ **Secure**: Limited permissions (only S3 access)
- ✅ **Reliable**: Credentials don't expire
- ✅ **Production-ready**: Standard practice for applications

Your main account stays MFA-protected, but the application gets seamless access to AWS services.

## 🔒 **Security Best Practices**

1. **Service User**: Only programmatic access, no console
2. **Minimal Permissions**: Only S3 access initially
3. **Credential Rotation**: Rotate keys every 90 days
4. **Environment Variables**: Store credentials in `.env` (gitignored)
5. **Monitoring**: Enable CloudTrail for API call logging

This approach gives you the best of both worlds: MFA security for your account and seamless application access!
