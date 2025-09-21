"""
AWS Configuration for Tarang Simulation Platform
"""

import os
from decouple import config

class AWSConfig:
    """AWS Configuration settings"""
    
    # AWS Credentials (should be set via environment variables or IAM roles)
    AWS_ACCESS_KEY_ID = config('AWS_ACCESS_KEY_ID', default=None)
    AWS_SECRET_ACCESS_KEY = config('AWS_SECRET_ACCESS_KEY', default=None)
    AWS_DEFAULT_REGION = config('AWS_DEFAULT_REGION', default='us-west-2')
    
    # S3 Configuration
    S3_BUCKET_NAME = config('TARANG_S3_BUCKET', default='tarang-simulations')
    S3_REGION = config('TARANG_S3_REGION', default=AWS_DEFAULT_REGION)
    
    # EKS Configuration
    EKS_CLUSTER_NAME = config('TARANG_EKS_CLUSTER', default='tarang-simulation-cluster')
    EKS_REGION = config('TARANG_EKS_REGION', default=AWS_DEFAULT_REGION)
    K8S_NAMESPACE = config('TARANG_K8S_NAMESPACE', default='tarang-simulations')
    
    # Docker Images
    DEFAULT_SIMULATION_IMAGE = config('TARANG_SIMULATION_IMAGE', default='tarang/simulator:latest')
    GPU_SIMULATION_IMAGE = config('TARANG_GPU_SIMULATION_IMAGE', default='tarang/simulator:gpu-latest')
    
    # Resource Limits
    DEFAULT_CPU_REQUEST = config('DEFAULT_CPU_REQUEST', default='2')
    DEFAULT_MEMORY_REQUEST = config('DEFAULT_MEMORY_REQUEST', default='4Gi')
    DEFAULT_CPU_LIMIT = config('DEFAULT_CPU_LIMIT', default='8')
    DEFAULT_MEMORY_LIMIT = config('DEFAULT_MEMORY_LIMIT', default='16Gi')
    
    MAX_CPU_LIMIT = config('MAX_CPU_LIMIT', default='32')
    MAX_MEMORY_LIMIT = config('MAX_MEMORY_LIMIT', default='128Gi')
    MAX_GPU_COUNT = config('MAX_GPU_COUNT', default=8, cast=int)
    
    # Job Configuration
    MAX_JOB_DURATION_HOURS = config('MAX_JOB_DURATION_HOURS', default=168, cast=int)  # 1 week
    JOB_CLEANUP_AFTER_HOURS = config('JOB_CLEANUP_AFTER_HOURS', default=24, cast=int)
    MAX_CONCURRENT_JOBS_PER_USER = config('MAX_CONCURRENT_JOBS_PER_USER', default=5, cast=int)
    
    # CloudWatch Configuration
    CLOUDWATCH_LOG_GROUP = config('CLOUDWATCH_LOG_GROUP', default='/aws/tarang/simulations')
    CLOUDWATCH_RETENTION_DAYS = config('CLOUDWATCH_RETENTION_DAYS', default=30, cast=int)
    
    # Cost Management
    ENABLE_COST_TRACKING = config('ENABLE_COST_TRACKING', default=True, cast=bool)
    COST_ALERT_THRESHOLD = config('COST_ALERT_THRESHOLD', default=100.0, cast=float)
    
    # Security
    ENABLE_NETWORK_POLICIES = config('ENABLE_NETWORK_POLICIES', default=True, cast=bool)
    ENABLE_POD_SECURITY_POLICIES = config('ENABLE_POD_SECURITY_POLICIES', default=True, cast=bool)
    
    @classmethod
    def validate_config(cls):
        """Validate AWS configuration"""
        errors = []
        
        # Check required AWS credentials (if not using IAM roles)
        if not cls.AWS_ACCESS_KEY_ID and not os.getenv('AWS_PROFILE'):
            errors.append("AWS_ACCESS_KEY_ID not set and no AWS_PROFILE found")
        
        if not cls.AWS_SECRET_ACCESS_KEY and not os.getenv('AWS_PROFILE'):
            errors.append("AWS_SECRET_ACCESS_KEY not set and no AWS_PROFILE found")
        
        # Check required configuration
        if not cls.S3_BUCKET_NAME:
            errors.append("S3_BUCKET_NAME is required")
        
        if not cls.EKS_CLUSTER_NAME:
            errors.append("EKS_CLUSTER_NAME is required")
        
        return errors
    
    @classmethod
    def get_job_resource_limits(cls, job_config):
        """Get resource limits for a job based on configuration"""
        cpu_request = job_config.get('cpu_request', cls.DEFAULT_CPU_REQUEST)
        memory_request = job_config.get('memory_request', cls.DEFAULT_MEMORY_REQUEST)
        cpu_limit = job_config.get('cpu_limit', cls.DEFAULT_CPU_LIMIT)
        memory_limit = job_config.get('memory_limit', cls.DEFAULT_MEMORY_LIMIT)
        gpu_count = min(job_config.get('gpu_count', 0), cls.MAX_GPU_COUNT)
        
        # Validate resource limits
        cpu_limit_int = int(cpu_limit.rstrip('m')) if cpu_limit.endswith('m') else int(cpu_limit)
        max_cpu_int = int(cls.MAX_CPU_LIMIT.rstrip('m')) if cls.MAX_CPU_LIMIT.endswith('m') else int(cls.MAX_CPU_LIMIT)
        
        if cpu_limit_int > max_cpu_int:
            cpu_limit = cls.MAX_CPU_LIMIT
        
        # Parse memory limits (simple validation)
        memory_limit_val = memory_limit.rstrip('Gi')
        max_memory_val = cls.MAX_MEMORY_LIMIT.rstrip('Gi')
        
        if int(memory_limit_val) > int(max_memory_val):
            memory_limit = cls.MAX_MEMORY_LIMIT
        
        return {
            'cpu_request': cpu_request,
            'memory_request': memory_request,
            'cpu_limit': cpu_limit,
            'memory_limit': memory_limit,
            'gpu_count': gpu_count
        }
    
    @classmethod
    def get_docker_image(cls, job_config):
        """Get appropriate Docker image based on job requirements"""
        if job_config.get('gpu_required', False):
            return job_config.get('image', cls.GPU_SIMULATION_IMAGE)
        else:
            return job_config.get('image', cls.DEFAULT_SIMULATION_IMAGE)

class KubernetesTemplates:
    """Kubernetes YAML templates for different job types"""
    
    @staticmethod
    def get_simulation_job_template():
        """Get Kubernetes Job template for simulations"""
        return """
apiVersion: batch/v1
kind: Job
metadata:
  name: {job_name}
  namespace: {namespace}
  labels:
    app: tarang-simulation
    username: {username}
    job-id: {job_id}
    job-type: simulation
spec:
  template:
    metadata:
      labels:
        app: tarang-simulation
        username: {username}
        job-id: {job_id}
    spec:
      restartPolicy: Never
      containers:
      - name: tarang-simulator
        image: {image}
        command: ["/bin/bash", "-c"]
        args:
        - |
          set -e
          echo "Starting Tarang simulation job {job_id} for user {username}"
          
          # Download para.py file from S3
          aws s3 cp s3://{s3_bucket}/{para_s3_key} /simulation_data/para.py
          
          # Download input files if specified
          if [ ! -z "{input_s3_prefix}" ]; then
            aws s3 sync s3://{s3_bucket}/{input_s3_prefix} /simulation_data/input/
          fi
          
          # Run simulation
          cd /simulation_data
          python /opt/tarang/tarang_simulator.py para.py
          
          # Upload results back to S3
          aws s3 sync /simulation_data/output/ s3://{s3_bucket}/{output_s3_prefix}
          
          # Upload logs
          aws s3 cp /simulation_data/simulation.log s3://{s3_bucket}/{log_s3_key}
          
          echo "Simulation job {job_id} completed successfully"
        resources:
          requests:
            cpu: {cpu_request}
            memory: {memory_request}
          limits:
            cpu: {cpu_limit}
            memory: {memory_limit}
        env:
        - name: AWS_DEFAULT_REGION
          value: {aws_region}
        - name: S3_BUCKET
          value: {s3_bucket}
        - name: JOB_ID
          value: {job_id}
        - name: USERNAME
          value: {username}
        - name: PARA_S3_KEY
          value: {para_s3_key}
        volumeMounts:
        - name: simulation-storage
          mountPath: /simulation_data
        - name: aws-credentials
          mountPath: /root/.aws
          readOnly: true
      volumes:
      - name: simulation-storage
        emptyDir: {{}}
      - name: aws-credentials
        secret:
          secretName: aws-credentials
  backoffLimit: 3
  ttlSecondsAfterFinished: {ttl_seconds}
"""
    
    @staticmethod
    def get_gpu_job_template():
        """Get Kubernetes Job template for GPU simulations"""
        return """
apiVersion: batch/v1
kind: Job
metadata:
  name: {job_name}
  namespace: {namespace}
  labels:
    app: tarang-simulation
    username: {username}
    job-id: {job_id}
    job-type: gpu-simulation
spec:
  template:
    metadata:
      labels:
        app: tarang-simulation
        username: {username}
        job-id: {job_id}
    spec:
      restartPolicy: Never
      nodeSelector:
        accelerator: nvidia-tesla-k80
      containers:
      - name: tarang-gpu-simulator
        image: {image}
        command: ["/bin/bash", "-c"]
        args:
        - |
          set -e
          echo "Starting GPU Tarang simulation job {job_id} for user {username}"
          
          # Check GPU availability
          nvidia-smi
          
          # Download para.py file from S3
          aws s3 cp s3://{s3_bucket}/{para_s3_key} /simulation_data/para.py
          
          # Run GPU simulation
          cd /simulation_data
          python /opt/tarang/tarang_gpu_simulator.py para.py
          
          # Upload results back to S3
          aws s3 sync /simulation_data/output/ s3://{s3_bucket}/{output_s3_prefix}
          
          echo "GPU simulation job {job_id} completed successfully"
        resources:
          requests:
            cpu: {cpu_request}
            memory: {memory_request}
            nvidia.com/gpu: {gpu_count}
          limits:
            cpu: {cpu_limit}
            memory: {memory_limit}
            nvidia.com/gpu: {gpu_count}
        env:
        - name: NVIDIA_VISIBLE_DEVICES
          value: all
        - name: NVIDIA_DRIVER_CAPABILITIES
          value: compute,utility
        - name: AWS_DEFAULT_REGION
          value: {aws_region}
        - name: S3_BUCKET
          value: {s3_bucket}
        - name: JOB_ID
          value: {job_id}
        - name: USERNAME
          value: {username}
        volumeMounts:
        - name: simulation-storage
          mountPath: /simulation_data
      volumes:
      - name: simulation-storage
        emptyDir: {{}}
  backoffLimit: 3
  ttlSecondsAfterFinished: {ttl_seconds}
"""

# Environment-specific configurations
class DevelopmentConfig(AWSConfig):
    """Development environment configuration"""
    S3_BUCKET_NAME = 'tarang-simulations-dev'
    EKS_CLUSTER_NAME = 'tarang-dev-cluster'
    MAX_CONCURRENT_JOBS_PER_USER = 2
    MAX_JOB_DURATION_HOURS = 24

class ProductionConfig(AWSConfig):
    """Production environment configuration"""
    S3_BUCKET_NAME = 'tarang-simulations-prod'
    EKS_CLUSTER_NAME = 'tarang-prod-cluster'
    ENABLE_COST_TRACKING = True
    ENABLE_NETWORK_POLICIES = True
    ENABLE_POD_SECURITY_POLICIES = True

class TestingConfig(AWSConfig):
    """Testing environment configuration"""
    S3_BUCKET_NAME = 'tarang-simulations-test'
    EKS_CLUSTER_NAME = 'tarang-test-cluster'
    MAX_CONCURRENT_JOBS_PER_USER = 1
    MAX_JOB_DURATION_HOURS = 1
    JOB_CLEANUP_AFTER_HOURS = 1

# Configuration factory
def get_config():
    """Get configuration based on environment"""
    env = os.getenv('FLASK_ENV', 'development')
    
    if env == 'production':
        return ProductionConfig
    elif env == 'testing':
        return TestingConfig
    else:
        return DevelopmentConfig
