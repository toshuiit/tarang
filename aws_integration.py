"""
AWS Integration for Tarang Simulation Platform
Handles S3 storage, EKS job management, and CloudWatch monitoring
"""

import boto3
import json
import os
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from botocore.exceptions import ClientError, NoCredentialsError
from flask import current_app
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class AWSSimulationManager:
    """Manages AWS resources for simulation platform"""
    
    def __init__(self):
        """Initialize AWS clients"""
        try:
            # Initialize AWS clients
            self.s3_client = boto3.client('s3')
            self.eks_client = boto3.client('eks')
            self.k8s_client = None  # Will be initialized when needed
            self.cloudwatch = boto3.client('cloudwatch')
            self.logs_client = boto3.client('logs')
            
            # Configuration
            self.bucket_name = os.getenv('TARANG_S3_BUCKET', 'tarang-simulations')
            self.cpu_cluster_name = os.getenv('TARANG_EKS_CPU_CLUSTER', 'tarang-cpu-cluster')
            self.gpu_cluster_name = os.getenv('TARANG_EKS_GPU_CLUSTER', 'tarang-gpu-cluster')
            self.region = os.getenv('AWS_DEFAULT_REGION', 'us-west-2')
            
            logger.info("AWS Simulation Manager initialized successfully")
            
        except NoCredentialsError:
            logger.error("AWS credentials not found. Please configure AWS credentials.")
            raise
        except Exception as e:
            logger.error(f"Failed to initialize AWS clients: {str(e)}")
            raise

    def setup_s3_bucket(self):
        """Create and configure S3 bucket for simulations"""
        try:
            # Check if bucket exists
            try:
                self.s3_client.head_bucket(Bucket=self.bucket_name)
                logger.info(f"S3 bucket {self.bucket_name} already exists")
            except ClientError as e:
                if e.response['Error']['Code'] == '404':
                    # Create bucket
                    self.s3_client.create_bucket(Bucket=self.bucket_name)
                    logger.info(f"Created S3 bucket: {self.bucket_name}")
                else:
                    raise
            
            # Set up bucket structure and lifecycle policies
            self._setup_bucket_lifecycle()
            return True
            
        except Exception as e:
            logger.error(f"Failed to setup S3 bucket: {str(e)}")
            return False

    def _setup_bucket_lifecycle(self):
        """Configure S3 bucket lifecycle policies"""
        lifecycle_config = {
            'Rules': [
                {
                    'ID': 'DeleteOldSimulations',
                    'Status': 'Enabled',
                    'Filter': {'Prefix': 'simulations/'},
                    'Expiration': {'Days': 90},  # Delete after 90 days
                    'Transitions': [
                        {
                            'Days': 30,
                            'StorageClass': 'STANDARD_IA'  # Move to cheaper storage after 30 days
                        },
                        {
                            'Days': 60,
                            'StorageClass': 'GLACIER'  # Archive after 60 days
                        }
                    ]
                }
            ]
        }
        
        try:
            self.s3_client.put_bucket_lifecycle_configuration(
                Bucket=self.bucket_name,
                LifecycleConfiguration=lifecycle_config
            )
            logger.info("S3 lifecycle policy configured")
        except Exception as e:
            logger.warning(f"Failed to set lifecycle policy: {str(e)}")

    def upload_user_para_file(self, username, para_content, job_id):
        """Upload user's para.py file to S3"""
        try:
            s3_key = f"users/{username}/para_files/para_{job_id}.py"
            
            self.s3_client.put_object(
                Bucket=self.bucket_name,
                Key=s3_key,
                Body=para_content,
                ContentType='text/plain',
                Metadata={
                    'username': username,
                    'job_id': job_id,
                    'upload_time': datetime.utcnow().isoformat(),
                    'file_type': 'para_file'
                }
            )
            
            logger.info(f"Uploaded para file for user {username}, job {job_id}")
            return s3_key
            
        except Exception as e:
            logger.error(f"Failed to upload para file: {str(e)}")
            raise

    def upload_simulation_data(self, username, job_id, file_path, file_type='output'):
        """Upload simulation output files to S3"""
        try:
            file_name = Path(file_path).name
            s3_key = f"simulations/{username}/{job_id}/{file_type}/{file_name}"
            
            self.s3_client.upload_file(
                file_path,
                self.bucket_name,
                s3_key,
                ExtraArgs={
                    'Metadata': {
                        'username': username,
                        'job_id': job_id,
                        'file_type': file_type,
                        'upload_time': datetime.utcnow().isoformat()
                    }
                }
            )
            
            logger.info(f"Uploaded {file_type} file: {file_name} for job {job_id}")
            return s3_key
            
        except Exception as e:
            logger.error(f"Failed to upload simulation data: {str(e)}")
            raise

    def get_presigned_download_url(self, s3_key, expiration=3600):
        """Generate presigned URL for downloading files"""
        try:
            url = self.s3_client.generate_presigned_url(
                'get_object',
                Params={'Bucket': self.bucket_name, 'Key': s3_key},
                ExpiresIn=expiration
            )
            return url
        except Exception as e:
            logger.error(f"Failed to generate presigned URL: {str(e)}")
            return None

    def list_user_files(self, username, job_id=None):
        """List files for a user or specific job"""
        try:
            if job_id:
                prefix = f"simulations/{username}/{job_id}/"
            else:
                prefix = f"simulations/{username}/"
            
            response = self.s3_client.list_objects_v2(
                Bucket=self.bucket_name,
                Prefix=prefix
            )
            
            files = []
            if 'Contents' in response:
                for obj in response['Contents']:
                    files.append({
                        'key': obj['Key'],
                        'size': obj['Size'],
                        'last_modified': obj['LastModified'].isoformat(),
                        'download_url': self.get_presigned_download_url(obj['Key'])
                    })
            
            return files
            
        except Exception as e:
            logger.error(f"Failed to list user files: {str(e)}")
            return []

class EKSJobManager:
    """Manages Kubernetes jobs on EKS for simulations"""
    
    def __init__(self, aws_manager):
        self.aws_manager = aws_manager
        self.k8s_clients = {}  # Store clients for both clusters
        self._initialize_k8s_clients()

    def _initialize_k8s_clients(self):
        """Initialize Kubernetes clients for both EKS clusters"""
        try:
            from kubernetes import client, config
            
            # Try to load kubeconfig (assumes eksctl has configured it)
            try:
                config.load_kube_config()
                
                # Create clients for both clusters
                self.k8s_clients['cpu'] = client.BatchV1Api()
                self.k8s_clients['gpu'] = client.BatchV1Api()
                
                logger.info("Kubernetes clients initialized for EKS clusters")
                
            except Exception as e:
                logger.warning(f"Could not load kubeconfig: {e}")
                # Fallback: clients will be None, jobs will be tracked in database only
                self.k8s_clients['cpu'] = None
                self.k8s_clients['gpu'] = None
                
        except Exception as e:
            logger.error(f"Failed to initialize Kubernetes clients: {str(e)}")
            self.k8s_clients['cpu'] = None
            self.k8s_clients['gpu'] = None

    def create_simulation_job(self, username, job_id, para_s3_key, job_config):
        """Create a Kubernetes job for simulation"""
        try:
            from kubernetes import client
            
            # Ensure user namespace exists
            user_namespace = f"tarang-user-{username}".lower()
            self._ensure_user_namespace(user_namespace, username)
            
            # Determine if this is a GPU job
            is_gpu_job = job_config.get('gpu_required', False)
            compute_type = job_config.get('compute_type', 'cpu')
            
            # Determine cluster and client
            if is_gpu_job or compute_type == 'gpu':
                cluster_type = 'gpu'
                cluster_name = self.aws_manager.gpu_cluster_name
            else:
                cluster_type = 'cpu'
                cluster_name = self.aws_manager.cpu_cluster_name
            
            # Check if Kubernetes client is available
            k8s_client = self.k8s_clients.get(cluster_type)
            if not k8s_client:
                logger.warning(f"Kubernetes client not available for {cluster_type} cluster. Job will be tracked in database only.")
                return f"tarang-{cluster_type}-{username}-{job_id}".lower()
            
            # Create job in appropriate cluster
            if cluster_type == 'gpu':
                return self._create_gpu_job(username, job_id, para_s3_key, job_config, user_namespace, k8s_client)
            else:
                return self._create_cpu_job(username, job_id, para_s3_key, job_config, user_namespace, k8s_client)
                
        except Exception as e:
            logger.error(f"Failed to create Kubernetes job: {str(e)}")
            raise

    def _ensure_user_namespace(self, namespace, username):
        """Ensure user namespace exists with proper isolation"""
        try:
            from kubernetes import client
            
            # Check if namespace exists
            v1 = client.CoreV1Api()
            try:
                v1.read_namespace(name=namespace)
                logger.info(f"Namespace {namespace} already exists")
                return
            except client.exceptions.ApiException as e:
                if e.status != 404:
                    raise
            
            # Create namespace
            namespace_body = client.V1Namespace(
                metadata=client.V1ObjectMeta(
                    name=namespace,
                    labels={
                        "user": username,
                        "app": "tarang-simulation",
                        "managed-by": "tarang-platform"
                    }
                )
            )
            v1.create_namespace(body=namespace_body)
            logger.info(f"Created namespace: {namespace}")
            
            # Create resource quota for the user
            self._create_user_resource_quota(namespace, username)
            
        except Exception as e:
            logger.error(f"Failed to ensure user namespace: {str(e)}")
            raise

    def _create_user_resource_quota(self, namespace, username):
        """Create resource quota for user namespace"""
        try:
            from kubernetes import client
            
            v1 = client.CoreV1Api()
            
            # Define resource limits per user
            quota_body = client.V1ResourceQuota(
                metadata=client.V1ObjectMeta(
                    name="user-quota",
                    namespace=namespace
                ),
                spec=client.V1ResourceQuotaSpec(
                    hard={
                        "requests.cpu": "16",           # Max 16 CPU cores per user
                        "requests.memory": "64Gi",      # Max 64GB RAM per user
                        "requests.nvidia.com/gpu": "4", # Max 4 GPUs per user
                        "pods": "10",                   # Max 10 concurrent jobs per user
                        "persistentvolumeclaims": "5"   # Max 5 PVCs per user
                    }
                )
            )
            
            try:
                v1.create_namespaced_resource_quota(namespace=namespace, body=quota_body)
                logger.info(f"Created resource quota for namespace: {namespace}")
            except client.exceptions.ApiException as e:
                if e.status == 409:  # Already exists
                    logger.info(f"Resource quota already exists for namespace: {namespace}")
                else:
                    raise
                    
        except Exception as e:
            logger.error(f"Failed to create resource quota: {str(e)}")
            # Don't fail job creation if quota creation fails
            pass

    def _create_cpu_job(self, username, job_id, para_s3_key, job_config, user_namespace, k8s_client):
        """Create a CPU-based Kubernetes job"""
        try:
            from kubernetes import client
            
            job_name = f"tarang-cpu-{username}-{job_id}".lower()
            
            # Job specification
            job_spec = client.V1Job(
                api_version="batch/v1",
                kind="Job",
                metadata=client.V1ObjectMeta(
                    name=job_name,
                    namespace=user_namespace,
                    labels={
                        "app": "tarang-simulation",
                        "username": username,
                        "job-id": job_id
                    }
                ),
                spec=client.V1JobSpec(
                    template=client.V1PodTemplateSpec(
                        metadata=client.V1ObjectMeta(
                            labels={
                                "app": "tarang-simulation",
                                "username": username,
                                "job-id": job_id
                            }
                        ),
                        spec=client.V1PodSpec(
                            restart_policy="Never",
                            containers=[
                                client.V1Container(
                                    name="tarang-simulator",
                                    image=job_config.get('image', 'tarang/simulator:latest'),
                                    command=["/bin/bash", "-c"],
                                    args=[self._generate_simulation_script(para_s3_key, job_id, username)],
                                    resources=client.V1ResourceRequirements(
                                        requests={
                                            "cpu": job_config.get('cpu_request', '2'),
                                            "memory": job_config.get('memory_request', '4Gi')
                                        },
                                        limits={
                                            "cpu": job_config.get('cpu_limit', '8'),
                                            "memory": job_config.get('memory_limit', '16Gi')
                                        }
                                    ),
                                    env=[
                                        client.V1EnvVar(name="AWS_DEFAULT_REGION", value=os.getenv('AWS_DEFAULT_REGION', 'us-west-2')),
                                        client.V1EnvVar(name="S3_BUCKET", value=self.aws_manager.bucket_name),
                                        client.V1EnvVar(name="JOB_ID", value=job_id),
                                        client.V1EnvVar(name="USERNAME", value=username),
                                        client.V1EnvVar(name="PARA_S3_KEY", value=para_s3_key)
                                    ],
                                    volume_mounts=[
                                        client.V1VolumeMount(
                                            name="simulation-storage",
                                            mount_path="/simulation_data"
                                        )
                                    ]
                                )
                            ],
                            volumes=[
                                client.V1Volume(
                                    name="simulation-storage",
                                    empty_dir=client.V1EmptyDirVolumeSource()
                                )
                            ]
                        )
                    ),
                    backoff_limit=3,
                    ttl_seconds_after_finished=86400  # Clean up after 24 hours
                )
            )
            
            # Create the job
            response = k8s_client.create_namespaced_job(
                namespace=user_namespace,
                body=job_spec
            )
            
            logger.info(f"Created CPU Kubernetes job: {job_name}")
            return job_name
            
        except Exception as e:
            logger.error(f"Failed to create CPU Kubernetes job: {str(e)}")
            raise

    def _create_gpu_job(self, username, job_id, para_s3_key, job_config, user_namespace, k8s_client):
        """Create a GPU-based Kubernetes job"""
        try:
            from kubernetes import client
            
            job_name = f"tarang-gpu-{username}-{job_id}".lower()
            
            # Job specification for GPU
            job_spec = client.V1Job(
                api_version="batch/v1",
                kind="Job",
                metadata=client.V1ObjectMeta(
                    name=job_name,
                    namespace=user_namespace,
                    labels={
                        "app": "tarang-simulation",
                        "username": username,
                        "job-id": job_id,
                        "compute-type": "gpu"
                    }
                ),
                spec=client.V1JobSpec(
                    template=client.V1PodTemplateSpec(
                        metadata=client.V1ObjectMeta(
                            labels={
                                "app": "tarang-simulation",
                                "username": username,
                                "job-id": job_id,
                                "compute-type": "gpu"
                            }
                        ),
                        spec=client.V1PodSpec(
                            restart_policy="Never",
                            node_selector={"accelerator": "nvidia-tesla-k80"},  # GPU nodes
                            containers=[
                                client.V1Container(
                                    name="tarang-gpu-simulator",
                                    image=job_config.get('image', 'tarang/simulator:gpu-latest'),
                                    command=["/bin/bash", "-c"],
                                    args=[self._generate_gpu_simulation_script(para_s3_key, job_id, username)],
                                    resources=client.V1ResourceRequirements(
                                        requests={
                                            "cpu": "4",
                                            "memory": "8Gi",
                                            "nvidia.com/gpu": "1"
                                        },
                                        limits={
                                            "cpu": "8",
                                            "memory": "16Gi",
                                            "nvidia.com/gpu": "1"
                                        }
                                    ),
                                    env=[
                                        client.V1EnvVar(name="NVIDIA_VISIBLE_DEVICES", value="all"),
                                        client.V1EnvVar(name="NVIDIA_DRIVER_CAPABILITIES", value="compute,utility"),
                                        client.V1EnvVar(name="AWS_DEFAULT_REGION", value=os.getenv('AWS_DEFAULT_REGION', 'us-west-2')),
                                        client.V1EnvVar(name="S3_BUCKET", value=self.aws_manager.bucket_name),
                                        client.V1EnvVar(name="JOB_ID", value=job_id),
                                        client.V1EnvVar(name="USERNAME", value=username),
                                        client.V1EnvVar(name="PARA_S3_KEY", value=para_s3_key),
                                        client.V1EnvVar(name="COMPUTE_TYPE", value="gpu")
                                    ],
                                    volume_mounts=[
                                        client.V1VolumeMount(
                                            name="simulation-storage",
                                            mount_path="/simulation_data"
                                        )
                                    ]
                                )
                            ],
                            volumes=[
                                client.V1Volume(
                                    name="simulation-storage",
                                    empty_dir=client.V1EmptyDirVolumeSource()
                                )
                            ]
                        )
                    ),
                    backoff_limit=3,
                    ttl_seconds_after_finished=86400  # Clean up after 24 hours
                )
            )
            
            # Create the job
            response = k8s_client.create_namespaced_job(
                namespace=user_namespace,
                body=job_spec
            )
            
            logger.info(f"Created GPU Kubernetes job: {job_name}")
            return job_name
            
        except Exception as e:
            logger.error(f"Failed to create GPU Kubernetes job: {str(e)}")
            raise

    def _generate_simulation_script(self, para_s3_key, job_id, username):
        """Generate the simulation execution script"""
        return f"""
        set -e
        echo "Starting Tarang simulation job {job_id} for user {username}"
        
        # Download para.py file from S3
        aws s3 cp s3://{self.aws_manager.bucket_name}/{para_s3_key} /simulation_data/para.py
        
        # Run simulation
        cd /simulation_data
        python /opt/tarang/tarang_simulator.py para.py
        
        # Upload results back to S3
        aws s3 sync /simulation_data/output/ s3://{self.aws_manager.bucket_name}/simulations/{username}/{job_id}/output/
        
        # Upload logs
        aws s3 cp /simulation_data/simulation.log s3://{self.aws_manager.bucket_name}/simulations/{username}/{job_id}/logs/
        
        echo "Simulation job {job_id} completed successfully"
        """

    def _generate_gpu_simulation_script(self, para_s3_key, job_id, username):
        """Generate the GPU simulation execution script"""
        return f"""
        set -e
        echo "Starting GPU Tarang simulation job {job_id} for user {username}"
        
        # Check GPU availability
        nvidia-smi
        
        # Download para.py file from S3
        aws s3 cp s3://{self.aws_manager.bucket_name}/{para_s3_key} /simulation_data/para.py
        
        # Run GPU simulation
        cd /simulation_data
        echo "Running GPU-accelerated Tarang simulation..."
        python /opt/tarang/tarang_gpu_simulator.py para.py
        
        # Upload results back to S3
        aws s3 sync /simulation_data/output/ s3://{self.aws_manager.bucket_name}/simulations/{username}/{job_id}/output/
        
        # Upload logs
        aws s3 cp /simulation_data/simulation.log s3://{self.aws_manager.bucket_name}/simulations/{username}/{job_id}/logs/
        
        echo "GPU simulation job {job_id} completed successfully"
        """

    def get_job_status(self, job_name):
        """Get status of a Kubernetes job"""
        try:
            response = self.k8s_client.read_namespaced_job_status(
                name=job_name,
                namespace=self.aws_manager.namespace
            )
            
            job = response
            status = {
                'name': job.metadata.name,
                'namespace': job.metadata.namespace,
                'creation_time': job.metadata.creation_timestamp.isoformat() if job.metadata.creation_timestamp else None,
                'active': job.status.active or 0,
                'succeeded': job.status.succeeded or 0,
                'failed': job.status.failed or 0,
                'conditions': []
            }
            
            if job.status.conditions:
                for condition in job.status.conditions:
                    status['conditions'].append({
                        'type': condition.type,
                        'status': condition.status,
                        'last_transition_time': condition.last_transition_time.isoformat() if condition.last_transition_time else None,
                        'reason': condition.reason,
                        'message': condition.message
                    })
            
            return status
            
        except Exception as e:
            logger.error(f"Failed to get job status: {str(e)}")
            return None

    def delete_job(self, job_name):
        """Delete a Kubernetes job"""
        try:
            from kubernetes import client
            
            self.k8s_client.delete_namespaced_job(
                name=job_name,
                namespace=self.aws_manager.namespace,
                body=client.V1DeleteOptions(
                    propagation_policy='Foreground'
                )
            )
            
            logger.info(f"Deleted Kubernetes job: {job_name}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to delete job: {str(e)}")
            return False

    def list_user_jobs(self, username):
        """List all jobs for a specific user"""
        try:
            response = self.k8s_client.list_namespaced_job(
                namespace=self.aws_manager.namespace,
                label_selector=f"username={username}"
            )
            
            jobs = []
            for job in response.items:
                job_info = {
                    'name': job.metadata.name,
                    'job_id': job.metadata.labels.get('job-id'),
                    'creation_time': job.metadata.creation_timestamp.isoformat() if job.metadata.creation_timestamp else None,
                    'active': job.status.active or 0,
                    'succeeded': job.status.succeeded or 0,
                    'failed': job.status.failed or 0,
                    'status': self._determine_job_status(job.status)
                }
                jobs.append(job_info)
            
            return jobs
            
        except Exception as e:
            logger.error(f"Failed to list user jobs: {str(e)}")
            return []

    def _determine_job_status(self, job_status):
        """Determine human-readable job status"""
        if job_status.succeeded and job_status.succeeded > 0:
            return "Completed"
        elif job_status.failed and job_status.failed > 0:
            return "Failed"
        elif job_status.active and job_status.active > 0:
            return "Running"
        else:
            return "Pending"

class CloudWatchMonitor:
    """Handles CloudWatch monitoring and logging"""
    
    def __init__(self, aws_manager):
        self.aws_manager = aws_manager
        self.cloudwatch = aws_manager.cloudwatch
        self.logs_client = aws_manager.logs_client
        self.log_group_name = '/aws/tarang/simulations'
        self._ensure_log_group_exists()

    def _ensure_log_group_exists(self):
        """Ensure CloudWatch log group exists"""
        try:
            self.logs_client.create_log_group(logGroupName=self.log_group_name)
            logger.info(f"Created CloudWatch log group: {self.log_group_name}")
        except self.logs_client.exceptions.ResourceAlreadyExistsException:
            pass  # Log group already exists
        except Exception as e:
            logger.error(f"Failed to create log group: {str(e)}")

    def put_custom_metric(self, metric_name, value, unit='Count', dimensions=None):
        """Put custom metric to CloudWatch"""
        try:
            metric_data = {
                'MetricName': metric_name,
                'Value': value,
                'Unit': unit,
                'Timestamp': datetime.utcnow()
            }
            
            if dimensions:
                metric_data['Dimensions'] = [
                    {'Name': k, 'Value': v} for k, v in dimensions.items()
                ]
            
            self.cloudwatch.put_metric_data(
                Namespace='Tarang/Simulations',
                MetricData=[metric_data]
            )
            
        except Exception as e:
            logger.error(f"Failed to put metric: {str(e)}")

    def log_simulation_event(self, username, job_id, event_type, message):
        """Log simulation events to CloudWatch"""
        try:
            log_stream_name = f"{username}/{job_id}"
            
            # Create log stream if it doesn't exist
            try:
                self.logs_client.create_log_stream(
                    logGroupName=self.log_group_name,
                    logStreamName=log_stream_name
                )
            except self.logs_client.exceptions.ResourceAlreadyExistsException:
                pass
            
            # Put log event
            self.logs_client.put_log_events(
                logGroupName=self.log_group_name,
                logStreamName=log_stream_name,
                logEvents=[
                    {
                        'timestamp': int(datetime.utcnow().timestamp() * 1000),
                        'message': f"[{event_type}] {message}"
                    }
                ]
            )
            
        except Exception as e:
            logger.error(f"Failed to log event: {str(e)}")

    def get_simulation_logs(self, username, job_id, start_time=None, end_time=None):
        """Retrieve simulation logs from CloudWatch"""
        try:
            log_stream_name = f"{username}/{job_id}"
            
            kwargs = {
                'logGroupName': self.log_group_name,
                'logStreamName': log_stream_name
            }
            
            if start_time:
                kwargs['startTime'] = int(start_time.timestamp() * 1000)
            if end_time:
                kwargs['endTime'] = int(end_time.timestamp() * 1000)
            
            response = self.logs_client.get_log_events(**kwargs)
            
            logs = []
            for event in response['events']:
                logs.append({
                    'timestamp': datetime.fromtimestamp(event['timestamp'] / 1000).isoformat(),
                    'message': event['message']
                })
            
            return logs
            
        except Exception as e:
            logger.error(f"Failed to get logs: {str(e)}")
            return []

# Utility functions
def initialize_aws_services():
    """Initialize all AWS services"""
    try:
        aws_manager = AWSSimulationManager()
        aws_manager.setup_s3_bucket()
        
        eks_manager = EKSJobManager(aws_manager)
        monitor = CloudWatchMonitor(aws_manager)
        
        return aws_manager, eks_manager, monitor
        
    except Exception as e:
        logger.error(f"Failed to initialize AWS services: {str(e)}")
        raise

def generate_job_id():
    """Generate unique job ID"""
    return str(uuid.uuid4())[:8]

def validate_job_config(config):
    """Validate job configuration"""
    required_fields = ['cpu_request', 'memory_request', 'image']
    for field in required_fields:
        if field not in config:
            raise ValueError(f"Missing required field: {field}")
    
    return True
