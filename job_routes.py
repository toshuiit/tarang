"""
Flask routes for job management and AWS integration
"""

from flask import Blueprint, request, jsonify, render_template, current_app, session
from flask_login import login_required, current_user
from datetime import datetime, timedelta
import json
import os
from pathlib import Path

from aws_integration import AWSSimulationManager, EKSJobManager, CloudWatchMonitor, generate_job_id
from job_models import (
    SimulationJob, JobLog, JobMetric, JobStatus, JobPriority,
    create_simulation_job, get_user_jobs, get_job_by_id, get_job_statistics
)
from models import db

# Create blueprint
jobs_bp = Blueprint('jobs', __name__, url_prefix='/jobs')

# Initialize AWS services (you might want to do this in app initialization)
try:
    aws_manager = AWSSimulationManager()
    eks_manager = EKSJobManager(aws_manager)
    monitor = CloudWatchMonitor(aws_manager)
except Exception as e:
    print(f"Warning: AWS services not available: {e}")
    aws_manager = None
    eks_manager = None
    monitor = None

@jobs_bp.route('/dashboard')
@login_required
def job_dashboard():
    """Job management dashboard"""
    user_jobs = get_user_jobs(current_user.id, limit=20)
    job_stats = get_job_statistics(current_user.id)
    
    return render_template('jobs/dashboard.html', 
                         jobs=user_jobs, 
                         stats=job_stats)

@jobs_bp.route('/create', methods=['POST'])
@login_required
def create_job():
    """Create a new simulation job"""
    try:
        # Get job configuration from request
        job_config = request.get_json()
        
        if not job_config:
            return jsonify({'success': False, 'error': 'No job configuration provided'}), 400
        
        # Validate required fields
        required_fields = ['name', 'simulation_config']
        for field in required_fields:
            if field not in job_config:
                return jsonify({'success': False, 'error': f'Missing required field: {field}'}), 400
        
        # Get user's current para.py content
        para_content = get_user_para_content()
        if not para_content:
            return jsonify({'success': False, 'error': 'No para.py configuration found'}), 400
        
        # Parse device from para.py content
        device_type = parse_device_from_para(para_content)
        
        # Update job config based on device type from para.py
        job_config.update({
            'compute_type': device_type.lower(),
            'cpu_request': '4' if device_type.upper() == 'GPU' else '2',
            'memory_request': '8Gi' if device_type.upper() == 'GPU' else '4Gi',
            'gpu_required': device_type.upper() == 'GPU',
            'gpu_count': 1 if device_type.upper() == 'GPU' else 0,
            'simulation_config': {
                'compute_type': device_type.lower(),
                'device': device_type.upper()
            }
        })
        
        # Create job in database
        job = create_simulation_job(current_user.id, job_config)
        
        # Upload para.py to S3
        if aws_manager:
            try:
                para_s3_key = aws_manager.upload_user_para_file(
                    current_user.username, 
                    para_content, 
                    job.job_id
                )
                job.para_s3_key = para_s3_key
                
                # Set S3 prefixes
                job.input_s3_prefix = f"simulations/{current_user.username}/{job.job_id}/input/"
                job.output_s3_prefix = f"simulations/{current_user.username}/{job.job_id}/output/"
                job.log_s3_key = f"simulations/{current_user.username}/{job.job_id}/logs/simulation.log"
                
                db.session.commit()
                
                # Log job creation
                monitor.log_simulation_event(
                    current_user.username, 
                    job.job_id, 
                    'JOB_CREATED', 
                    f'Job {job.name} created and para.py uploaded to S3'
                )
                
            except Exception as e:
                job.update_status(JobStatus.FAILED.value, f"Failed to upload para.py: {str(e)}")
                db.session.commit()
                return jsonify({'success': False, 'error': f'Failed to upload configuration: {str(e)}'}), 500
        
        # Create Kubernetes job
        if eks_manager:
            try:
                k8s_job_name = eks_manager.create_simulation_job(
                    current_user.username,
                    job.job_id,
                    job.para_s3_key,
                    {
                        'image': job_config.get('image', 'tarang/simulator:latest'),
                        'cpu_request': job.cpu_request,
                        'memory_request': job.memory_request,
                        'cpu_limit': job.cpu_limit,
                        'memory_limit': job.memory_limit
                    }
                )
                
                job.k8s_job_name = k8s_job_name
                job.update_status(JobStatus.QUEUED.value)
                db.session.commit()
                
                # Log job queued
                monitor.log_simulation_event(
                    current_user.username, 
                    job.job_id, 
                    'JOB_QUEUED', 
                    f'Kubernetes job {k8s_job_name} created'
                )
                
            except Exception as e:
                job.update_status(JobStatus.FAILED.value, f"Failed to create Kubernetes job: {str(e)}")
                db.session.commit()
                return jsonify({'success': False, 'error': f'Failed to start job: {str(e)}'}), 500
        
        return jsonify({
            'success': True,
            'job_id': job.job_id,
            'message': 'Job created successfully',
            'job': job.to_dict()
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@jobs_bp.route('/list')
@login_required
def list_jobs():
    """List user's jobs with filtering and pagination"""
    try:
        # Get query parameters
        status = request.args.get('status')
        limit = min(int(request.args.get('limit', 50)), 100)
        offset = int(request.args.get('offset', 0))
        
        # Get jobs
        jobs = get_user_jobs(current_user.id, status=status, limit=limit, offset=offset)
        
        # Convert to dict format
        jobs_data = [job.to_dict() for job in jobs]
        
        return jsonify({
            'success': True,
            'jobs': jobs_data,
            'total': len(jobs_data),
            'limit': limit,
            'offset': offset
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@jobs_bp.route('/<job_id>')
@login_required
def get_job_details(job_id):
    """Get detailed job information"""
    try:
        job = get_job_by_id(job_id)
        
        if not job:
            return jsonify({'success': False, 'error': 'Job not found'}), 404
        
        # Check if user owns this job
        if job.user_id != current_user.id:
            return jsonify({'success': False, 'error': 'Access denied'}), 403
        
        # Get additional details
        job_data = job.to_dict()
        
        # Get recent logs
        recent_logs = JobLog.query.filter_by(job_id=job.id)\
                                .order_by(JobLog.timestamp.desc())\
                                .limit(50).all()
        job_data['recent_logs'] = [log.to_dict() for log in recent_logs]
        
        # Get recent metrics
        recent_metrics = JobMetric.query.filter_by(job_id=job.id)\
                                      .order_by(JobMetric.timestamp.desc())\
                                      .limit(100).all()
        job_data['recent_metrics'] = [metric.to_dict() for metric in recent_metrics]
        
        # Get Kubernetes status if available
        if eks_manager and job.k8s_job_name:
            try:
                k8s_status = eks_manager.get_job_status(job.k8s_job_name)
                job_data['kubernetes_status'] = k8s_status
            except Exception as e:
                job_data['kubernetes_status'] = {'error': str(e)}
        
        # Get S3 files if available
        if aws_manager:
            try:
                files = aws_manager.list_user_files(current_user.username, job.job_id)
                job_data['files'] = files
            except Exception as e:
                job_data['files'] = []
        
        return jsonify({
            'success': True,
            'job': job_data
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@jobs_bp.route('/<job_id>/status')
@login_required
def get_job_status(job_id):
    """Get current job status"""
    try:
        job = get_job_by_id(job_id)
        
        if not job or job.user_id != current_user.id:
            return jsonify({'success': False, 'error': 'Job not found'}), 404
        
        # Update status from Kubernetes if available
        if eks_manager and job.k8s_job_name and job.is_running:
            try:
                k8s_status = eks_manager.get_job_status(job.k8s_job_name)
                
                # Update job status based on Kubernetes status
                if k8s_status:
                    if k8s_status['succeeded'] > 0:
                        job.update_status(JobStatus.COMPLETED.value)
                    elif k8s_status['failed'] > 0:
                        job.update_status(JobStatus.FAILED.value, "Job failed in Kubernetes")
                    elif k8s_status['active'] > 0:
                        job.update_status(JobStatus.RUNNING.value)
                    
                    db.session.commit()
                    
            except Exception as e:
                print(f"Failed to get Kubernetes status: {e}")
        
        return jsonify({
            'success': True,
            'job_id': job.job_id,
            'status': job.status,
            'progress_percentage': job.progress_percentage,
            'current_step': job.current_step,
            'duration_minutes': job.duration_minutes,
            'error_message': job.error_message
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@jobs_bp.route('/<job_id>/cancel', methods=['POST'])
@login_required
def cancel_job(job_id):
    """Cancel a running job"""
    try:
        job = get_job_by_id(job_id)
        
        if not job or job.user_id != current_user.id:
            return jsonify({'success': False, 'error': 'Job not found'}), 404
        
        if job.is_finished:
            return jsonify({'success': False, 'error': 'Job is already finished'}), 400
        
        # Cancel Kubernetes job
        if eks_manager and job.k8s_job_name:
            try:
                eks_manager.delete_job(job.k8s_job_name)
                
                # Log cancellation
                if monitor:
                    monitor.log_simulation_event(
                        current_user.username, 
                        job.job_id, 
                        'JOB_CANCELLED', 
                        f'Job cancelled by user'
                    )
                
            except Exception as e:
                print(f"Failed to cancel Kubernetes job: {e}")
        
        # Update job status
        job.update_status(JobStatus.CANCELLED.value, "Cancelled by user")
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'Job cancelled successfully'
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@jobs_bp.route('/<job_id>/logs')
@login_required
def get_job_logs(job_id):
    """Get job logs"""
    try:
        job = get_job_by_id(job_id)
        
        if not job or job.user_id != current_user.id:
            return jsonify({'success': False, 'error': 'Job not found'}), 404
        
        # Get query parameters
        limit = min(int(request.args.get('limit', 100)), 1000)
        level = request.args.get('level')  # Filter by log level
        
        # Get logs from database
        query = JobLog.query.filter_by(job_id=job.id)
        
        if level:
            query = query.filter_by(level=level.upper())
        
        logs = query.order_by(JobLog.timestamp.desc()).limit(limit).all()
        logs_data = [log.to_dict() for log in logs]
        
        # Get CloudWatch logs if available
        if monitor:
            try:
                cloudwatch_logs = monitor.get_simulation_logs(
                    current_user.username, 
                    job.job_id,
                    start_time=datetime.utcnow() - timedelta(hours=24)
                )
                
                # Merge with database logs
                for cw_log in cloudwatch_logs:
                    logs_data.append({
                        'level': 'INFO',
                        'message': cw_log['message'],
                        'timestamp': cw_log['timestamp'],
                        'source': 'cloudwatch'
                    })
                
                # Sort by timestamp
                logs_data.sort(key=lambda x: x['timestamp'], reverse=True)
                
            except Exception as e:
                print(f"Failed to get CloudWatch logs: {e}")
        
        return jsonify({
            'success': True,
            'logs': logs_data[:limit]  # Ensure we don't exceed limit
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@jobs_bp.route('/<job_id>/files')
@login_required
def get_job_files(job_id):
    """Get job files from S3"""
    try:
        job = get_job_by_id(job_id)
        
        if not job or job.user_id != current_user.id:
            return jsonify({'success': False, 'error': 'Job not found'}), 404
        
        if not aws_manager:
            return jsonify({'success': False, 'error': 'S3 not available'}), 503
        
        # Get files from S3
        files = aws_manager.list_user_files(current_user.username, job.job_id)
        
        return jsonify({
            'success': True,
            'files': files
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@jobs_bp.route('/<job_id>/download/<path:file_path>')
@login_required
def download_job_file(job_id, file_path):
    """Generate download URL for job file"""
    try:
        job = get_job_by_id(job_id)
        
        if not job or job.user_id != current_user.id:
            return jsonify({'success': False, 'error': 'Job not found'}), 404
        
        if not aws_manager:
            return jsonify({'success': False, 'error': 'S3 not available'}), 503
        
        # Construct S3 key
        s3_key = f"simulations/{current_user.username}/{job.job_id}/{file_path}"
        
        # Generate presigned URL
        download_url = aws_manager.get_presigned_download_url(s3_key, expiration=3600)
        
        if not download_url:
            return jsonify({'success': False, 'error': 'Failed to generate download URL'}), 500
        
        return jsonify({
            'success': True,
            'download_url': download_url
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@jobs_bp.route('/statistics')
@login_required
def get_user_statistics():
    """Get user's job statistics"""
    try:
        stats = get_job_statistics(current_user.id)
        
        # Get additional statistics
        recent_jobs = get_user_jobs(current_user.id, limit=10)
        
        # Calculate average duration
        completed_jobs = [job for job in recent_jobs if job.actual_duration]
        avg_duration = sum(job.actual_duration for job in completed_jobs) / len(completed_jobs) if completed_jobs else 0
        
        stats.update({
            'average_duration_minutes': round(avg_duration, 2),
            'recent_jobs': [job.to_dict() for job in recent_jobs[:5]]
        })
        
        return jsonify({
            'success': True,
            'statistics': stats
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

# Utility functions
def get_user_para_content():
    """Get user's current para.py content"""
    try:
        from app import get_user_para_path
        para_path = get_user_para_path()
        
        if Path(para_path).exists():
            return Path(para_path).read_text()
        else:
            return None
            
    except Exception as e:
        print(f"Failed to get para content: {e}")
        return None

def parse_device_from_para(para_content):
    """Parse device type from para.py content"""
    try:
        # Look for device = 'CPU' or device = 'GPU' in para.py
        import re
        
        # Search for device assignment
        device_match = re.search(r"device\s*=\s*['\"]([^'\"]+)['\"]", para_content)
        if device_match:
            device = device_match.group(1).upper()
            return device if device in ['CPU', 'GPU'] else 'CPU'
        
        # Default to CPU if not found
        return 'CPU'
        
    except Exception as e:
        print(f"Failed to parse device from para.py: {e}")
        return 'CPU'

# Background task for monitoring jobs (you might want to use Celery for this)
def monitor_running_jobs():
    """Monitor running jobs and update their status"""
    if not eks_manager:
        return
    
    try:
        running_jobs = SimulationJob.query.filter(
            SimulationJob.status.in_([JobStatus.RUNNING.value, JobStatus.QUEUED.value])
        ).all()
        
        for job in running_jobs:
            if job.k8s_job_name:
                try:
                    k8s_status = eks_manager.get_job_status(job.k8s_job_name)
                    
                    if k8s_status:
                        # Update job status based on Kubernetes status
                        if k8s_status['succeeded'] > 0:
                            job.update_status(JobStatus.COMPLETED.value)
                        elif k8s_status['failed'] > 0:
                            job.update_status(JobStatus.FAILED.value, "Job failed in Kubernetes")
                        elif k8s_status['active'] > 0 and job.status != JobStatus.RUNNING.value:
                            job.update_status(JobStatus.RUNNING.value)
                        
                        db.session.commit()
                        
                except Exception as e:
                    print(f"Failed to monitor job {job.job_id}: {e}")
                    
    except Exception as e:
        print(f"Failed to monitor jobs: {e}")

# Register error handlers
@jobs_bp.errorhandler(404)
def not_found(error):
    return jsonify({'success': False, 'error': 'Resource not found'}), 404

@jobs_bp.errorhandler(403)
def forbidden(error):
    return jsonify({'success': False, 'error': 'Access forbidden'}), 403

@jobs_bp.errorhandler(500)
def internal_error(error):
    return jsonify({'success': False, 'error': 'Internal server error'}), 500
