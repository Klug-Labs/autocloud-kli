"""
Monitoring and Observability Module

Provides comprehensive monitoring, logging, and observability features for Lambda functions.
"""

import asyncio
import json
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
import click
from .utils import ConfigManager, log_header, log_step, log_success, log_error, log_info, log_detail


class CloudWatchManager:
    """Manages CloudWatch logs and metrics"""
    
    def __init__(self, config: ConfigManager):
        self.config = config
        self.logs_client = config.session.client('logs')
        self.cloudwatch_client = config.session.client('cloudwatch')
    
    async def get_function_logs(self, function_name: str, lines: int = 50) -> List[Dict]:
        """Get recent logs for a Lambda function"""
        try:
            log_group_name = f"/aws/lambda/{function_name}"
            
            # Get log streams
            streams_response = self.logs_client.describe_log_streams(
                logGroupName=log_group_name,
                orderBy='LastEventTime',
                descending=True,
                limit=5
            )
            
            log_entries = []
            
            for stream in streams_response.get('logStreams', []):
                # Get log events
                events_response = self.logs_client.get_log_events(
                    logGroupName=log_group_name,
                    logStreamName=stream['logStreamName'],
                    limit=lines
                )
                
                for event in events_response.get('events', []):
                    log_entries.append({
                        'timestamp': datetime.fromtimestamp(event['timestamp'] / 1000),
                        'message': event['message'],
                        'stream': stream['logStreamName']
                    })
            
            # Sort by timestamp
            log_entries.sort(key=lambda x: x['timestamp'], reverse=True)
            
            return log_entries[:lines]
            
        except Exception as e:
            log_error(f"Failed to get logs for {function_name}: {e}")
            return []
    
    async def get_function_metrics(self, function_name: str, hours: int = 24) -> Dict[str, List]:
        """Get CloudWatch metrics for a Lambda function"""
        try:
            end_time = datetime.utcnow()
            start_time = end_time - timedelta(hours=hours)
            
            metrics = {}
            
            # Define metric names
            metric_names = [
                'Invocations',
                'Errors',
                'Duration',
                'Throttles',
                'ConcurrentExecutions'
            ]
            
            for metric_name in metric_names:
                response = self.cloudwatch_client.get_metric_statistics(
                    Namespace='AWS/Lambda',
                    MetricName=metric_name,
                    Dimensions=[
                        {
                            'Name': 'FunctionName',
                            'Value': function_name
                        }
                    ],
                    StartTime=start_time,
                    EndTime=end_time,
                    Period=3600,  # 1 hour periods
                    Statistics=['Sum', 'Average', 'Maximum']
                )
                
                metrics[metric_name] = response.get('Datapoints', [])
            
            return metrics
            
        except Exception as e:
            log_error(f"Failed to get metrics for {function_name}: {e}")
            return {}
    
    async def create_log_group(self, function_name: str) -> bool:
        """Create CloudWatch log group for a function"""
        try:
            log_group_name = f"/aws/lambda/{function_name}"
            
            # Check if log group exists
            try:
                self.logs_client.describe_log_groups(logGroupNamePrefix=log_group_name)
                log_info(f"Log group already exists: {log_group_name}")
                return True
            except self.logs_client.exceptions.ResourceNotFoundException:
                pass
            
            # Create log group
            self.logs_client.create_log_group(logGroupName=log_group_name)
            
            # Set retention policy
            retention_days = int(self.config.tool_config.get('LOG_RETENTION_DAYS', 14))
            self.logs_client.put_retention_policy(
                logGroupName=log_group_name,
                retentionInDays=retention_days
            )
            
            log_success(f"Created log group: {log_group_name}")
            return True
            
        except Exception as e:
            log_error(f"Failed to create log group for {function_name}: {e}")
            return False


class AlarmManager:
    """Manages CloudWatch alarms"""
    
    def __init__(self, config: ConfigManager):
        self.config = config
        self.cloudwatch_client = config.session.client('cloudwatch')
    
    async def create_function_alarms(self, function_name: str) -> bool:
        """Create CloudWatch alarms for a Lambda function"""
        try:
            log_info(f"Creating alarms for function: {function_name}")
            
            # Error rate alarm
            await self._create_error_rate_alarm(function_name)
            
            # Duration alarm
            await self._create_duration_alarm(function_name)
            
            # Throttle alarm
            await self._create_throttle_alarm(function_name)
            
            log_success(f"Created alarms for function: {function_name}")
            return True
            
        except Exception as e:
            log_error(f"Failed to create alarms for {function_name}: {e}")
            return False
    
    async def _create_error_rate_alarm(self, function_name: str):
        """Create error rate alarm"""
        alarm_name = f"{function_name}-error-rate"
        
        self.cloudwatch_client.put_metric_alarm(
            AlarmName=alarm_name,
            ComparisonOperator='GreaterThanThreshold',
            EvaluationPeriods=2,
            MetricName='Errors',
            Namespace='AWS/Lambda',
            Period=300,  # 5 minutes
            Statistic='Sum',
            Threshold=5.0,
            ActionsEnabled=True,
            AlarmActions=[],  # Add SNS topic ARN if configured
            AlarmDescription=f'High error rate for {function_name}',
            Dimensions=[
                {
                    'Name': 'FunctionName',
                    'Value': function_name
                }
            ]
        )
        
        log_detail(f"Created error rate alarm: {alarm_name}")
    
    async def _create_duration_alarm(self, function_name: str):
        """Create duration alarm"""
        alarm_name = f"{function_name}-duration"
        
        # Get function timeout from configuration
        timeout_ms = int(self.config.tool_config.get('LAMBDA_TIMEOUT', 30)) * 1000
        
        self.cloudwatch_client.put_metric_alarm(
            AlarmName=alarm_name,
            ComparisonOperator='GreaterThanThreshold',
            EvaluationPeriods=2,
            MetricName='Duration',
            Namespace='AWS/Lambda',
            Period=300,  # 5 minutes
            Statistic='Average',
            Threshold=timeout_ms * 0.8,  # 80% of timeout
            ActionsEnabled=True,
            AlarmActions=[],  # Add SNS topic ARN if configured
            AlarmDescription=f'High duration for {function_name}',
            Dimensions=[
                {
                    'Name': 'FunctionName',
                    'Value': function_name
                }
            ]
        )
        
        log_detail(f"Created duration alarm: {alarm_name}")
    
    async def _create_throttle_alarm(self, function_name: str):
        """Create throttle alarm"""
        alarm_name = f"{function_name}-throttles"
        
        self.cloudwatch_client.put_metric_alarm(
            AlarmName=alarm_name,
            ComparisonOperator='GreaterThanThreshold',
            EvaluationPeriods=1,
            MetricName='Throttles',
            Namespace='AWS/Lambda',
            Period=300,  # 5 minutes
            Statistic='Sum',
            Threshold=1.0,
            ActionsEnabled=True,
            AlarmActions=[],  # Add SNS topic ARN if configured
            AlarmDescription=f'Function throttling detected for {function_name}',
            Dimensions=[
                {
                    'Name': 'FunctionName',
                    'Value': function_name
                }
            ]
        )
        
        log_detail(f"Created throttle alarm: {alarm_name}")


class XRayManager:
    """Manages X-Ray tracing"""
    
    def __init__(self, config: ConfigManager):
        self.config = config
        self.lambda_client = config.session.client('lambda')
    
    async def enable_xray_tracing(self, function_name: str) -> bool:
        """Enable X-Ray tracing for a Lambda function"""
        try:
            if not self.config.tool_config.get('ENABLE_XRAY', 'false').lower() == 'true':
                log_info("X-Ray tracing disabled in configuration")
                return True
            
            # Update function configuration
            self.lambda_client.update_function_configuration(
                FunctionName=function_name,
                TracingConfig={
                    'Mode': 'Active'
                }
            )
            
            log_success(f"Enabled X-Ray tracing for function: {function_name}")
            return True
            
        except Exception as e:
            log_error(f"Failed to enable X-Ray tracing for {function_name}: {e}")
            return False
    
    async def disable_xray_tracing(self, function_name: str) -> bool:
        """Disable X-Ray tracing for a Lambda function"""
        try:
            # Update function configuration
            self.lambda_client.update_function_configuration(
                FunctionName=function_name,
                TracingConfig={
                    'Mode': 'PassThrough'
                }
            )
            
            log_success(f"Disabled X-Ray tracing for function: {function_name}")
            return True
            
        except Exception as e:
            log_error(f"Failed to disable X-Ray tracing for {function_name}: {e}")
            return False


class DashboardManager:
    """Manages CloudWatch dashboards"""
    
    def __init__(self, config: ConfigManager):
        self.config = config
        self.cloudwatch_client = config.session.client('cloudwatch')
    
    async def create_function_dashboard(self, function_name: str) -> bool:
        """Create CloudWatch dashboard for a Lambda function"""
        try:
            dashboard_name = f"{function_name}-dashboard"
            
            # Create dashboard widgets
            widgets = [
                {
                    "type": "metric",
                    "x": 0,
                    "y": 0,
                    "width": 12,
                    "height": 6,
                    "properties": {
                        "metrics": [
                            ["AWS/Lambda", "Invocations", "FunctionName", function_name],
                            [".", "Errors", ".", "."],
                            [".", "Throttles", ".", "."]
                        ],
                        "view": "timeSeries",
                        "stacked": False,
                        "region": self.config.tool_config.get('AWS_REGION', 'us-east-1'),
                        "title": f"{function_name} - Invocations, Errors, Throttles",
                        "period": 300
                    }
                },
                {
                    "type": "metric",
                    "x": 12,
                    "y": 0,
                    "width": 12,
                    "height": 6,
                    "properties": {
                        "metrics": [
                            ["AWS/Lambda", "Duration", "FunctionName", function_name],
                            [".", "ConcurrentExecutions", ".", "."]
                        ],
                        "view": "timeSeries",
                        "stacked": False,
                        "region": self.config.tool_config.get('AWS_REGION', 'us-east-1'),
                        "title": f"{function_name} - Duration and Concurrency",
                        "period": 300
                    }
                }
            ]
            
            # Create dashboard
            self.cloudwatch_client.put_dashboard(
                DashboardName=dashboard_name,
                DashboardBody=json.dumps({
                    "widgets": widgets
                })
            )
            
            log_success(f"Created dashboard: {dashboard_name}")
            return True
            
        except Exception as e:
            log_error(f"Failed to create dashboard for {function_name}: {e}")
            return False


class MonitoringManager:
    """Main monitoring manager that orchestrates all monitoring features"""
    
    def __init__(self, config: ConfigManager):
        self.config = config
        self.cloudwatch_manager = CloudWatchManager(config)
        self.alarm_manager = AlarmManager(config)
        self.xray_manager = XRayManager(config)
        self.dashboard_manager = DashboardManager(config)
    
    async def setup_monitoring(self, function_names: List[str]) -> bool:
        """Setup comprehensive monitoring for all functions"""
        log_header("MONITORING & OBSERVABILITY SETUP")
        
        success_count = 0
        
        for function_name in function_names:
            log_step("SETUP", f"Setting up monitoring for: {function_name}")
            
            # Create log groups
            if await self.cloudwatch_manager.create_log_group(function_name):
                success_count += 1
            
            # Create alarms
            if await self.alarm_manager.create_function_alarms(function_name):
                success_count += 1
            
            # Enable X-Ray tracing
            if await self.xray_manager.enable_xray_tracing(function_name):
                success_count += 1
            
            # Create dashboard
            if await self.dashboard_manager.create_function_dashboard(function_name):
                success_count += 1
        
        log_success(f"Monitoring setup completed for {len(function_names)} functions")
        return success_count > 0
    
    async def get_monitoring_status(self, function_name: str) -> Dict[str, Any]:
        """Get monitoring status for a function"""
        try:
            status = {
                'function_name': function_name,
                'logs_available': False,
                'alarms_configured': False,
                'xray_enabled': False,
                'dashboard_created': False
            }
            
            # Check log group
            try:
                log_group_name = f"/aws/lambda/{function_name}"
                self.cloudwatch_manager.logs_client.describe_log_groups(
                    logGroupNamePrefix=log_group_name
                )
                status['logs_available'] = True
            except:
                pass
            
            # Check alarms
            try:
                alarms_response = self.cloudwatch_manager.cloudwatch_client.describe_alarms(
                    AlarmNamePrefix=function_name
                )
                status['alarms_configured'] = len(alarms_response.get('MetricAlarms', [])) > 0
            except:
                pass
            
            # Check X-Ray tracing
            try:
                function_response = self.xray_manager.lambda_client.get_function_configuration(
                    FunctionName=function_name
                )
                tracing_config = function_response.get('TracingConfig', {})
                status['xray_enabled'] = tracing_config.get('Mode') == 'Active'
            except:
                pass
            
            return status
            
        except Exception as e:
            log_error(f"Failed to get monitoring status for {function_name}: {e}")
            return {'function_name': function_name, 'error': str(e)}


# CLI Commands for monitoring
@click.command()
@click.option('--tool', '-t', 
              help='Path to .tool configuration file (auto-detected if not provided)')
@click.option('--env', '-e', 
              help='Path to .env file for environment variables (auto-detected if not provided)')
@click.option('--function-name', '-f',
              help='Specific function name to setup monitoring for')
def setup_monitoring(tool, env, function_name):
    """📊 Setup monitoring and observability for Lambda functions"""
    try:
        from .utils import detect_project_context, find_best_config_files
        
        # Auto-detect configuration if not provided
        if not tool or not env:
            context = detect_project_context()
            detected_tool, detected_env = find_best_config_files(context)
            tool = tool or detected_tool
            env = env or detected_env
        
        config = ConfigManager(tool, env)
        
        # Get function names
        if function_name:
            function_names = [function_name]
        else:
            # Get all functions (this would need to be implemented)
            function_names = [f"{config.app_name}-{config.infra}-main"]
        
        # Setup monitoring
        manager = MonitoringManager(config)
        success = asyncio.run(manager.setup_monitoring(function_names))
        
        if success:
            click.echo(click.style("✅ Monitoring setup completed successfully!", fg='green'))
        else:
            click.echo(click.style("❌ Monitoring setup failed!", fg='red'))
            sys.exit(1)
            
    except Exception as e:
        click.echo(click.style(f"❌ Monitoring setup error: {e}", fg='red'))
        sys.exit(1)


@click.command()
@click.option('--tool', '-t', 
              help='Path to .tool configuration file (auto-detected if not provided)')
@click.option('--env', '-e', 
              help='Path to .env file for environment variables (auto-detected if not provided)')
@click.option('--function-name', '-f',
              help='Specific function name to check monitoring for')
def monitoring_status(tool, env, function_name):
    """📈 Check monitoring status for Lambda functions"""
    try:
        from .utils import detect_project_context, find_best_config_files
        
        # Auto-detect configuration if not provided
        if not tool or not env:
            context = detect_project_context()
            detected_tool, detected_env = find_best_config_files(context)
            tool = tool or detected_tool
            env = env or detected_env
        
        config = ConfigManager(tool, env)
        
        # Get function names
        if function_name:
            function_names = [function_name]
        else:
            function_names = [f"{config.app_name}-{config.infra}-main"]
        
        # Check monitoring status
        manager = MonitoringManager(config)
        
        for func_name in function_names:
            status = asyncio.run(manager.get_monitoring_status(func_name))
            
            click.echo(click.style(f"📊 Monitoring Status for {func_name}", fg='blue', bold=True))
            click.echo(f"  Logs Available: {'✅' if status.get('logs_available') else '❌'}")
            click.echo(f"  Alarms Configured: {'✅' if status.get('alarms_configured') else '❌'}")
            click.echo(f"  X-Ray Enabled: {'✅' if status.get('xray_enabled') else '❌'}")
            click.echo(f"  Dashboard Created: {'✅' if status.get('dashboard_created') else '❌'}")
            
    except Exception as e:
        click.echo(click.style(f"❌ Monitoring status error: {e}", fg='red'))
        sys.exit(1)
