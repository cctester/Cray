""" AWS plugin for Cray - provides AWS cloud services integration.

All boto3 calls are run in a thread executor to avoid blocking the async event loop.
"""

import asyncio
from typing import Dict, Any
from loguru import logger

try:
    import boto3
    BOTO3_AVAILABLE = True
except ImportError:
    BOTO3_AVAILABLE = False
    boto3 = None

from cray.plugins import Plugin


class AWSPlugin(Plugin):
    """Plugin for AWS cloud services integration."""

    name = "aws"
    description = "AWS cloud services integration - S3, EC2, Lambda, and more"

    @property
    def actions(self):
        return {
            "s3_get": {"description": "Get S3 object", "params": [
                {"name": "bucket", "type": "string", "required": True, "description": "S3 bucket"},
                {"name": "key", "type": "string", "required": True, "description": "Object key"},
            ]},
            "s3_put": {"description": "Put S3 object", "params": [
                {"name": "bucket", "type": "string", "required": True, "description": "S3 bucket"},
                {"name": "key", "type": "string", "required": True, "description": "Object key"},
                {"name": "body", "type": "string", "required": True, "description": "Content"},
            ]},
            "ec2_list": {"description": "List EC2 instances", "params": []},
            "lambda_invoke": {"description": "Invoke Lambda", "params": [
                {"name": "function_name", "type": "string", "required": True, "description": "Function name"},
                {"name": "payload", "type": "object", "required": False, "description": "Payload"},
            ]},
        }

    def __init__(self):
        super().__init__()
        self.sessions = {}

    async def execute(
        self, action: str, params: Dict[str, Any], context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Execute an AWS action."""
        if not BOTO3_AVAILABLE:
            return {
                "success": False,
                "error": "AWS plugin requires 'boto3' package. Install with: pip install boto3"
            }

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

    async def _run_sync(self, func, *args):
        """Run a synchronous boto3 call in a thread executor."""
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, lambda: func(*args))

    async def _s3_upload(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Upload a file to S3."""
        try:
            bucket = params.get("bucket")
            key = params.get("key")
            file_path = params.get("file_path")
            region = params.get("region", "us-east-1")

            if not all([bucket, key, file_path]):
                raise ValueError("Missing required parameters: bucket, key, file_path")

            def _upload():
                s3 = boto3.client("s3", region_name=region)
                s3.upload_file(file_path, bucket, key)

            await self._run_sync(_upload)

            return {
                "success": True,
                "bucket": bucket,
                "key": key,
                "file_path": file_path
            }
        except Exception as e:
            logger.error(f"Failed to upload to S3: {e}")
            return {"success": False, "error": str(e)}

    async def _s3_download(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Download a file from S3."""
        try:
            bucket = params.get("bucket")
            key = params.get("key")
            file_path = params.get("file_path")
            region = params.get("region", "us-east-1")

            if not all([bucket, key, file_path]):
                raise ValueError("Missing required parameters: bucket, key, file_path")

            def _download():
                s3 = boto3.client("s3", region_name=region)
                s3.download_file(bucket, key, file_path)

            await self._run_sync(_download)

            return {
                "success": True,
                "bucket": bucket,
                "key": key,
                "file_path": file_path
            }
        except Exception as e:
            logger.error(f"Failed to download from S3: {e}")
            return {"success": False, "error": str(e)}

    async def _s3_list(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """List objects in an S3 bucket."""
        try:
            bucket = params.get("bucket")
            prefix = params.get("prefix", "")
            region = params.get("region", "us-east-1")

            if not bucket:
                raise ValueError("Missing required parameter: bucket")

            def _list():
                s3 = boto3.client("s3", region_name=region)
                response = s3.list_objects_v2(Bucket=bucket, Prefix=prefix)
                objects = []
                for obj in response.get("Contents", []):
                    objects.append({
                        "key": obj["Key"],
                        "size": obj["Size"],
                        "last_modified": obj["LastModified"].isoformat()
                    })
                return objects

            objects = await self._run_sync(_list)

            return {
                "success": True,
                "bucket": bucket,
                "objects": objects,
                "count": len(objects)
            }
        except Exception as e:
            logger.error(f"Failed to list S3 objects: {e}")
            return {"success": False, "error": str(e)}

    async def _s3_delete(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Delete an object from S3."""
        try:
            bucket = params.get("bucket")
            key = params.get("key")
            region = params.get("region", "us-east-1")

            if not all([bucket, key]):
                raise ValueError("Missing required parameters: bucket, key")

            def _delete():
                s3 = boto3.client("s3", region_name=region)
                s3.delete_object(Bucket=bucket, Key=key)

            await self._run_sync(_delete)

            return {"success": True, "bucket": bucket, "key": key}
        except Exception as e:
            logger.error(f"Failed to delete S3 object: {e}")
            return {"success": False, "error": str(e)}

    async def _ec2_start(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Start an EC2 instance."""
        try:
            instance_id = params.get("instance_id")
            region = params.get("region", "us-east-1")

            if not instance_id:
                raise ValueError("Missing required parameter: instance_id")

            def _start():
                ec2 = boto3.client("ec2", region_name=region)
                return ec2.start_instances(InstanceIds=[instance_id])

            response = await self._run_sync(_start)

            return {
                "success": True,
                "instance_id": instance_id,
                "response": response
            }
        except Exception as e:
            logger.error(f"Failed to start EC2 instance: {e}")
            return {"success": False, "error": str(e)}

    async def _ec2_stop(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Stop an EC2 instance."""
        try:
            instance_id = params.get("instance_id")
            region = params.get("region", "us-east-1")

            if not instance_id:
                raise ValueError("Missing required parameter: instance_id")

            def _stop():
                ec2 = boto3.client("ec2", region_name=region)
                return ec2.stop_instances(InstanceIds=[instance_id])

            response = await self._run_sync(_stop)

            return {
                "success": True,
                "instance_id": instance_id,
                "response": response
            }
        except Exception as e:
            logger.error(f"Failed to stop EC2 instance: {e}")
            return {"success": False, "error": str(e)}

    async def _ec2_list(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """List EC2 instances."""
        try:
            region = params.get("region", "us-east-1")
            state = params.get("state", "running")

            def _list():
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
                return instances

            instances = await self._run_sync(_list)

            return {
                "success": True,
                "instances": instances,
                "count": len(instances)
            }
        except Exception as e:
            logger.error(f"Failed to list EC2 instances: {e}")
            return {"success": False, "error": str(e)}

    async def _lambda_invoke(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Invoke a Lambda function."""
        try:
            function_name = params.get("function_name")
            payload = params.get("payload", {})
            region = params.get("region", "us-east-1")

            if not function_name:
                raise ValueError("Missing required parameter: function_name")

            def _invoke():
                lambda_client = boto3.client("lambda", region_name=region)
                response = lambda_client.invoke(
                    FunctionName=function_name,
                    Payload=str(payload)
                )
                payload_data = response.get("Payload", None)
                payload_str = payload_data.read().decode() if payload_data else ""
                return response["StatusCode"], payload_str

            status_code, payload_str = await self._run_sync(_invoke)

            return {
                "success": True,
                "function_name": function_name,
                "status_code": status_code,
                "response": payload_str
            }
        except Exception as e:
            logger.error(f"Failed to invoke Lambda function: {e}")
            return {"success": False, "error": str(e)}

    async def _sqs_send(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Send a message to an SQS queue."""
        try:
            queue_url = params.get("queue_url")
            message_body = params.get("message_body")
            region = params.get("region", "us-east-1")

            if not all([queue_url, message_body]):
                raise ValueError("Missing required parameters: queue_url, message_body")

            def _send():
                sqs = boto3.client("sqs", region_name=region)
                return sqs.send_message(QueueUrl=queue_url, MessageBody=message_body)

            response = await self._run_sync(_send)

            return {
                "success": True,
                "queue_url": queue_url,
                "message_id": response["MessageId"]
            }
        except Exception as e:
            logger.error(f"Failed to send SQS message: {e}")
            return {"success": False, "error": str(e)}

    async def _sqs_receive(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Receive messages from an SQS queue."""
        try:
            queue_url = params.get("queue_url")
            max_messages = params.get("max_messages", 1)
            region = params.get("region", "us-east-1")

            if not queue_url:
                raise ValueError("Missing required parameter: queue_url")

            def _receive():
                sqs = boto3.client("sqs", region_name=region)
                return sqs.receive_message(
                    QueueUrl=queue_url,
                    MaxNumberOfMessages=max_messages
                )

            response = await self._run_sync(_receive)
            messages = response.get("Messages", [])

            return {
                "success": True,
                "queue_url": queue_url,
                "messages": messages,
                "count": len(messages)
            }
        except Exception as e:
            logger.error(f"Failed to receive SQS messages: {e}")
            return {"success": False, "error": str(e)}
