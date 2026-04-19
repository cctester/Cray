"""
AWS plugin for Cray - provides AWS cloud services integration.
"""
import boto3
import asyncio
from typing import Dict, Any
from loguru import logger

from cray.plugins import Plugin


class AWSPlugin(Plugin):
    """Plugin for AWS cloud services integration."""
    
    name = "aws"
    description = "AWS cloud services integration - S3, EC2, Lambda, and more"
    
    @property
    def actions(self):
        return {
            "s3_get": {"description": "Get S3 object", "params": [{"name": "bucket", "type": "string", "required": True, "description": "S3 bucket"}, {"name": "key", "type": "string", "required": True, "description": "Object key"}]},
            "s3_put": {"description": "Put S3 object", "params": [{"name": "bucket", "type": "string", "required": True, "description": "S3 bucket"}, {"name": "key", "type": "string", "required": True, "description": "Object key"}, {"name": "body", "type": "string", "required": True, "description": "Content"}]},
            "ec2_list": {"description": "List EC2 instances", "params": []},
            "lambda_invoke": {"description": "Invoke Lambda", "params": [{"name": "function_name", "type": "string", "required": True, "description": "Function name"}, {"name": "payload", "type": "object", "required": False, "description": "Payload"}]},
        }
    
    def __init__(self):
        super().__init__()
        self.sessions = {}
    
    async def execute(
        self,
        action: str,
        params: Dict[str, Any],
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Execute an AWS action."""
        
        actions = {
            "s3_upload": self._s3_upload,
            "s3_download": self._s3_download,
            "s3_list": self._s3_list,
            "s3_delete": self._s3_delete,
            "ec2_start": self._ec2_start,
            "ec2_stop": self._ec2_stop,
            "ec2_list": self._ec2_list,
            "lambda_invoke": self._lambda_invoke,
            "sqs_send": self._sqs_send,
            "sqs_receive": self._sqs_receive,
        }
        
        if action not in actions:
            raise ValueError(f"Unknown action: {action}")
        
        return await actions[action](params)
    
    async def _s3_upload(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Upload a file to S3."""
        try:
            bucket = params.get("bucket")
            key = params.get("key")
            file_path = params.get("file_path")
            region = params.get("region", "us-east-1")
            
            if not all([bucket, key, file_path]):
                raise ValueError("Missing required parameters: bucket, key, file_path")
            
            s3 = boto3.client("s3", region_name=region)
            s3.upload_file(file_path, bucket, key)
            
            return {
                "success": True,
                "bucket": bucket,
                "key": key,
                "file_path": file_path
            }
        except Exception as e:
            logger.error(f"Failed to upload to S3: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def _s3_download(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Download a file from S3."""
        try:
            bucket = params.get("bucket")
            key = params.get("key")
            file_path = params.get("file_path")
            region = params.get("region", "us-east-1")
            
            if not all([bucket, key, file_path]):
                raise ValueError("Missing required parameters: bucket, key, file_path")
            
            s3 = boto3.client("s3", region_name=region)
            s3.download_file(bucket, key, file_path)
            
            return {
                "success": True,
                "bucket": bucket,
                "key": key,
                "file_path": file_path
            }
        except Exception as e:
            logger.error(f"Failed to download from S3: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def _s3_list(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """List objects in an S3 bucket."""
        try:
            bucket = params.get("bucket")
            prefix = params.get("prefix", "")
            region = params.get("region", "us-east-1")
            
            if not bucket:
                raise ValueError("Missing required parameter: bucket")
            
            s3 = boto3.client("s3", region_name=region)
            response = s3.list_objects_v2(Bucket=bucket, Prefix=prefix)
            
            objects = []
            if "Contents" in response:
                objects = [obj["Key"] for obj in response["Contents"]]
            
            return {
                "success": True,
                "bucket": bucket,
                "objects": objects,
                "count": len(objects)
            }
        except Exception as e:
            logger.error(f"Failed to list S3 objects: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def _s3_delete(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Delete an object from S3."""
        try:
            bucket = params.get("bucket")
            key = params.get("key")
            region = params.get("region", "us-east-1")
            
            if not all([bucket, key]):
                raise ValueError("Missing required parameters: bucket, key")
            
            s3 = boto3.client("s3", region_name=region)
            s3.delete_object(Bucket=bucket, Key=key)
            
            return {
                "success": True,
                "bucket": bucket,
                "key": key
            }
        except Exception as e:
            logger.error(f"Failed to delete S3 object: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def _ec2_start(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Start an EC2 instance."""
        try:
            instance_id = params.get("instance_id")
            region = params.get("region", "us-east-1")
            
            if not instance_id:
                raise ValueError("Missing required parameter: instance_id")
            
            ec2 = boto3.client("ec2", region_name=region)
            response = ec2.start_instances(InstanceIds=[instance_id])
            
            return {
                "success": True,
                "instance_id": instance_id,
                "response": response
            }
        except Exception as e:
            logger.error(f"Failed to start EC2 instance: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def _ec2_stop(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Stop an EC2 instance."""
        try:
            instance_id = params.get("instance_id")
            region = params.get("region", "us-east-1")
            
            if not instance_id:
                raise ValueError("Missing required parameter: instance_id")
            
            ec2 = boto3.client("ec2", region_name=region)
            response = ec2.stop_instances(InstanceIds=[instance_id])
            
            return {
                "success": True,
                "instance_id": instance_id,
                "response": response
            }
        except Exception as e:
            logger.error(f"Failed to stop EC2 instance: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def _ec2_list(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """List EC2 instances."""
        try:
            region = params.get("region", "us-east-1")
            state = params.get("state", "running")
            
            ec2 = boto3.client("ec2", region_name=region)
            response = ec2.describe_instances(
                Filters=[{"Name": "instance-state-name", "Values": [state]}]
            )
            
            instances = []
            for reservation in response["Reservations"]:
                for instance in reservation["Instances"]:
                    instances.append({
                        "instance_id": instance["InstanceId"],
                        "state": instance["State"]["Name"],
                        "instance_type": instance["InstanceType"],
                        "public_ip": instance.get("PublicIpAddress", "N/A"),
                    })
            
            return {
                "success": True,
                "instances": instances,
                "count": len(instances)
            }
        except Exception as e:
            logger.error(f"Failed to list EC2 instances: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def _lambda_invoke(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Invoke a Lambda function."""
        try:
            function_name = params.get("function_name")
            payload = params.get("payload", {})
            region = params.get("region", "us-east-1")
            
            if not function_name:
                raise ValueError("Missing required parameter: function_name")
            
            lambda_client = boto3.client("lambda", region_name=region)
            response = lambda_client.invoke(
                FunctionName=function_name,
                Payload=str(payload)
            )
            
            return {
                "success": True,
                "function_name": function_name,
                "status_code": response["StatusCode"],
                "response": response.get("Payload", {}).read().decode()
            }
        except Exception as e:
            logger.error(f"Failed to invoke Lambda function: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def _sqs_send(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Send a message to an SQS queue."""
        try:
            queue_url = params.get("queue_url")
            message_body = params.get("message_body")
            region = params.get("region", "us-east-1")
            
            if not all([queue_url, message_body]):
                raise ValueError("Missing required parameters: queue_url, message_body")
            
            sqs = boto3.client("sqs", region_name=region)
            response = sqs.send_message(
                QueueUrl=queue_url,
                MessageBody=message_body
            )
            
            return {
                "success": True,
                "queue_url": queue_url,
                "message_id": response["MessageId"]
            }
        except Exception as e:
            logger.error(f"Failed to send SQS message: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def _sqs_receive(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Receive messages from an SQS queue."""
        try:
            queue_url = params.get("queue_url")
            max_messages = params.get("max_messages", 1)
            region = params.get("region", "us-east-1")
            
            if not queue_url:
                raise ValueError("Missing required parameter: queue_url")
            
            sqs = boto3.client("sqs", region_name=region)
            response = sqs.receive_message(
                QueueUrl=queue_url,
                MaxNumberOfMessages=max_messages
            )
            
            messages = response.get("Messages", [])
            
            return {
                "success": True,
                "queue_url": queue_url,
                "messages": messages,
                "count": len(messages)
            }
        except Exception as e:
            logger.error(f"Failed to receive SQS messages: {e}")
            return {
                "success": False,
                "error": str(e)
            }