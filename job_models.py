"""
Database models for job tracking and management
"""

from datetime import datetime, timedelta
from sqlalchemy import Column, Integer, String, DateTime, Text, Boolean, Float, ForeignKey, JSON
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from models import db
import enum

class JobStatus(enum.Enum):
    """Job status enumeration"""
    PENDING = "pending"
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    TIMEOUT = "timeout"

class JobPriority(enum.Enum):
    """Job priority enumeration"""
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    URGENT = "urgent"

class SimulationJob(db.Model):
    """Model for tracking simulation jobs"""
    __tablename__ = 'simulation_jobs'
    
    id = Column(Integer, primary_key=True)
    job_id = Column(String(50), unique=True, nullable=False, index=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    
    # Job metadata
    name = Column(String(200), nullable=False)
    description = Column(Text)
    status = Column(String(20), default=JobStatus.PENDING.value, index=True)
    priority = Column(String(20), default=JobPriority.NORMAL.value)
    
    # Timing information
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    started_at = Column(DateTime)
    completed_at = Column(DateTime)
    estimated_duration = Column(Integer)  # in minutes
    actual_duration = Column(Integer)     # in minutes
    
    # Resource configuration
    cpu_request = Column(String(10), default='2')
    memory_request = Column(String(10), default='4Gi')
    cpu_limit = Column(String(10), default='8')
    memory_limit = Column(String(10), default='16Gi')
    gpu_required = Column(Boolean, default=False)
    gpu_count = Column(Integer, default=0)
    
    # File locations
    para_s3_key = Column(String(500))
    input_s3_prefix = Column(String(500))
    output_s3_prefix = Column(String(500))
    log_s3_key = Column(String(500))
    
    # Kubernetes information
    k8s_job_name = Column(String(100))
    k8s_namespace = Column(String(100), default='tarang-simulations')
    
    # Progress and monitoring
    progress_percentage = Column(Float, default=0.0)
    current_step = Column(String(200))
    total_steps = Column(Integer)
    error_message = Column(Text)
    
    # Simulation parameters (stored as JSON)
    simulation_config = Column(JSON)
    
    # Cost tracking
    estimated_cost = Column(Float)
    actual_cost = Column(Float)
    
    # Relationships
    user = relationship("User", backref="simulation_jobs")
    job_logs = relationship("JobLog", backref="job", cascade="all, delete-orphan")
    job_metrics = relationship("JobMetric", backref="job", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f'<SimulationJob {self.job_id}: {self.name}>'
    
    @property
    def duration_minutes(self):
        """Calculate job duration in minutes"""
        if self.started_at and self.completed_at:
            return int((self.completed_at - self.started_at).total_seconds() / 60)
        elif self.started_at:
            return int((datetime.utcnow() - self.started_at).total_seconds() / 60)
        return 0
    
    @property
    def is_running(self):
        """Check if job is currently running"""
        return self.status in [JobStatus.RUNNING.value, JobStatus.QUEUED.value]
    
    @property
    def is_finished(self):
        """Check if job is finished (completed, failed, or cancelled)"""
        return self.status in [JobStatus.COMPLETED.value, JobStatus.FAILED.value, JobStatus.CANCELLED.value, JobStatus.TIMEOUT.value]
    
    def update_status(self, new_status, error_message=None):
        """Update job status with timestamp"""
        old_status = self.status
        self.status = new_status
        
        if new_status == JobStatus.RUNNING.value and not self.started_at:
            self.started_at = datetime.utcnow()
        elif new_status in [JobStatus.COMPLETED.value, JobStatus.FAILED.value, JobStatus.CANCELLED.value, JobStatus.TIMEOUT.value]:
            if not self.completed_at:
                self.completed_at = datetime.utcnow()
                self.actual_duration = self.duration_minutes
        
        if error_message:
            self.error_message = error_message
        
        # Log status change
        log_entry = JobLog(
            job_id=self.id,
            level='INFO',
            message=f'Status changed from {old_status} to {new_status}',
            timestamp=datetime.utcnow()
        )
        db.session.add(log_entry)
    
    def update_progress(self, percentage, current_step=None):
        """Update job progress"""
        self.progress_percentage = min(100.0, max(0.0, percentage))
        if current_step:
            self.current_step = current_step
    
    def to_dict(self):
        """Convert job to dictionary for JSON serialization"""
        return {
            'id': self.id,
            'job_id': self.job_id,
            'name': self.name,
            'description': self.description,
            'status': self.status,
            'priority': self.priority,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'started_at': self.started_at.isoformat() if self.started_at else None,
            'completed_at': self.completed_at.isoformat() if self.completed_at else None,
            'duration_minutes': self.duration_minutes,
            'progress_percentage': self.progress_percentage,
            'current_step': self.current_step,
            'total_steps': self.total_steps,
            'cpu_request': self.cpu_request,
            'memory_request': self.memory_request,
            'gpu_required': self.gpu_required,
            'gpu_count': self.gpu_count,
            'error_message': self.error_message,
            'estimated_cost': self.estimated_cost,
            'actual_cost': self.actual_cost,
            'simulation_config': self.simulation_config
        }

class JobLog(db.Model):
    """Model for job logs"""
    __tablename__ = 'job_logs'
    
    id = Column(Integer, primary_key=True)
    job_id = Column(Integer, ForeignKey('simulation_jobs.id'), nullable=False)
    level = Column(String(20), nullable=False)  # INFO, WARNING, ERROR, DEBUG
    message = Column(Text, nullable=False)
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)
    source = Column(String(50))  # kubernetes, aws, application
    
    def __repr__(self):
        return f'<JobLog {self.level}: {self.message[:50]}...>'
    
    def to_dict(self):
        return {
            'id': self.id,
            'level': self.level,
            'message': self.message,
            'timestamp': self.timestamp.isoformat(),
            'source': self.source
        }

class JobMetric(db.Model):
    """Model for job performance metrics"""
    __tablename__ = 'job_metrics'
    
    id = Column(Integer, primary_key=True)
    job_id = Column(Integer, ForeignKey('simulation_jobs.id'), nullable=False)
    metric_name = Column(String(100), nullable=False)
    metric_value = Column(Float, nullable=False)
    unit = Column(String(20))
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)
    
    def __repr__(self):
        return f'<JobMetric {self.metric_name}: {self.metric_value} {self.unit}>'
    
    def to_dict(self):
        return {
            'id': self.id,
            'metric_name': self.metric_name,
            'metric_value': self.metric_value,
            'unit': self.unit,
            'timestamp': self.timestamp.isoformat()
        }

class JobQueue(db.Model):
    """Model for job queue management"""
    __tablename__ = 'job_queue'
    
    id = Column(Integer, primary_key=True)
    job_id = Column(Integer, ForeignKey('simulation_jobs.id'), nullable=False, unique=True)
    queue_position = Column(Integer, nullable=False)
    estimated_start_time = Column(DateTime)
    resource_requirements = Column(JSON)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    job = relationship("SimulationJob", backref="queue_entry")
    
    def __repr__(self):
        return f'<JobQueue position {self.queue_position}: job {self.job_id}>'

class ResourceUsage(db.Model):
    """Model for tracking resource usage"""
    __tablename__ = 'resource_usage'
    
    id = Column(Integer, primary_key=True)
    job_id = Column(Integer, ForeignKey('simulation_jobs.id'), nullable=False)
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)
    
    # CPU metrics
    cpu_usage_percent = Column(Float)
    cpu_cores_used = Column(Float)
    
    # Memory metrics
    memory_usage_bytes = Column(Integer)
    memory_usage_percent = Column(Float)
    
    # GPU metrics (if applicable)
    gpu_usage_percent = Column(Float)
    gpu_memory_usage_bytes = Column(Integer)
    
    # Network metrics
    network_in_bytes = Column(Integer)
    network_out_bytes = Column(Integer)
    
    # Storage metrics
    disk_usage_bytes = Column(Integer)
    disk_io_read_bytes = Column(Integer)
    disk_io_write_bytes = Column(Integer)
    
    job = relationship("SimulationJob", backref="resource_usage")
    
    def to_dict(self):
        return {
            'timestamp': self.timestamp.isoformat(),
            'cpu_usage_percent': self.cpu_usage_percent,
            'cpu_cores_used': self.cpu_cores_used,
            'memory_usage_bytes': self.memory_usage_bytes,
            'memory_usage_percent': self.memory_usage_percent,
            'gpu_usage_percent': self.gpu_usage_percent,
            'gpu_memory_usage_bytes': self.gpu_memory_usage_bytes,
            'network_in_bytes': self.network_in_bytes,
            'network_out_bytes': self.network_out_bytes,
            'disk_usage_bytes': self.disk_usage_bytes
        }

# Utility functions for job management
def create_simulation_job(user_id, job_config):
    """Create a new simulation job"""
    from aws_integration import generate_job_id
    
    job = SimulationJob(
        job_id=generate_job_id(),
        user_id=user_id,
        name=job_config.get('name', 'Untitled Simulation'),
        description=job_config.get('description', ''),
        priority=job_config.get('priority', JobPriority.NORMAL.value),
        cpu_request=job_config.get('cpu_request', '2'),
        memory_request=job_config.get('memory_request', '4Gi'),
        cpu_limit=job_config.get('cpu_limit', '8'),
        memory_limit=job_config.get('memory_limit', '16Gi'),
        gpu_required=job_config.get('gpu_required', False),
        gpu_count=job_config.get('gpu_count', 0),
        estimated_duration=job_config.get('estimated_duration', 60),
        simulation_config=job_config.get('simulation_config', {}),
        total_steps=job_config.get('total_steps', 100)
    )
    
    db.session.add(job)
    db.session.commit()
    
    return job

def get_user_jobs(user_id, status=None, limit=50, offset=0):
    """Get jobs for a specific user"""
    query = SimulationJob.query.filter_by(user_id=user_id)
    
    if status:
        query = query.filter_by(status=status)
    
    return query.order_by(SimulationJob.created_at.desc()).offset(offset).limit(limit).all()

def get_job_by_id(job_id):
    """Get job by job_id"""
    return SimulationJob.query.filter_by(job_id=job_id).first()

def get_running_jobs():
    """Get all currently running jobs"""
    return SimulationJob.query.filter(
        SimulationJob.status.in_([JobStatus.RUNNING.value, JobStatus.QUEUED.value])
    ).all()

def cleanup_old_jobs(days=30):
    """Clean up old completed jobs"""
    cutoff_date = datetime.utcnow() - timedelta(days=days)
    
    old_jobs = SimulationJob.query.filter(
        SimulationJob.completed_at < cutoff_date,
        SimulationJob.status.in_([JobStatus.COMPLETED.value, JobStatus.FAILED.value, JobStatus.CANCELLED.value])
    ).all()
    
    for job in old_jobs:
        db.session.delete(job)
    
    db.session.commit()
    return len(old_jobs)

def get_job_statistics(user_id=None):
    """Get job statistics"""
    query = SimulationJob.query
    
    if user_id:
        query = query.filter_by(user_id=user_id)
    
    total_jobs = query.count()
    running_jobs = query.filter_by(status=JobStatus.RUNNING.value).count()
    completed_jobs = query.filter_by(status=JobStatus.COMPLETED.value).count()
    failed_jobs = query.filter_by(status=JobStatus.FAILED.value).count()
    
    return {
        'total_jobs': total_jobs,
        'running_jobs': running_jobs,
        'completed_jobs': completed_jobs,
        'failed_jobs': failed_jobs,
        'success_rate': (completed_jobs / total_jobs * 100) if total_jobs > 0 else 0
    }
