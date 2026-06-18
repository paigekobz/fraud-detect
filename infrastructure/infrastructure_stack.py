from aws_cdk import (
    Stack,
    Duration,
    RemovalPolicy,
    aws_ec2 as ec2,
    aws_ecs as ecs,
    aws_ecs_patterns as ecs_patterns,
    aws_sqs as sqs,
    aws_lambda as lambda_,
    aws_lambda_event_sources as lambda_events,
    aws_dynamodb as dynamodb,
    aws_iam as iam,
    aws_ecr_assets as ecr_assets,
    aws_cloudwatch as cloudwatch,
    aws_cloudwatch_actions as cw_actions,
    aws_sns as sns,
    aws_sns_subscriptions as subscriptions,
)
from constructs import Construct
import os

class InfrastructureStack(Stack):

    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        vpc = ec2.Vpc(self, "FraudDetectionVpc", max_azs=2)

        fraud_queue = sqs.Queue(
            self, "FraudQueue",
            queue_name="fraud-detection-queue",
            visibility_timeout=Duration.seconds(30),
        )

        fraud_table = dynamodb.Table(
            self, "FraudTable",
            table_name="fraud-logs",
            partition_key=dynamodb.Attribute(
                name="transaction_id",
                type=dynamodb.AttributeType.STRING
            ),
            removal_policy=RemovalPolicy.DESTROY,
        )

        cluster = ecs.Cluster(
            self, "FraudCluster",
            vpc=vpc
        )

        docker_image = ecr_assets.DockerImageAsset(
            self, "FraudAppImage",
            directory="..",
        )

        fargate_service = ecs_patterns.ApplicationLoadBalancedFargateService(
            self, "FraudFargateService",
            cluster=cluster,
            cpu=256,
            memory_limit_mib=512,
            desired_count=1,
            task_image_options=ecs_patterns.ApplicationLoadBalancedTaskImageOptions(
                image=ecs.ContainerImage.from_docker_image_asset(docker_image),
                container_port=8000,
                environment={
                    "SQS_QUEUE_URL": fraud_queue.queue_url,
                    "AWS_REGION": self.region,
                }
            ),
            public_load_balancer=True,
        )

        fargate_service.target_group.configure_health_check(path="/health")

        fraud_queue.grant_send_messages(fargate_service.task_definition.task_role)

        fraud_lambda = lambda_.Function(
            self, "FraudLambda",
            runtime=lambda_.Runtime.PYTHON_3_11,
            handler="handler.handler",
            code=lambda_.Code.from_asset("../lambda"),
            timeout=Duration.seconds(30),
            environment={
                "DYNAMODB_TABLE": fraud_table.table_name,
                "SENDER_EMAIL": "paige.kobzar@gmail.com",
                "RECIPIENT_EMAIL": "paige.kobzar@gmail.com",
            }
        )

        fraud_lambda.add_event_source(
            lambda_events.SqsEventSource(
                fraud_queue,
                batch_size=1,
            )
        )

        fraud_table.grant_write_data(fraud_lambda)
        fraud_queue.grant_consume_messages(fraud_lambda)

        fraud_lambda.add_to_role_policy(
            iam.PolicyStatement(
                actions=["ses:SendEmail", "ses:SendRawEmail"],
                resources=["*"]
            )
        )

        # CloudWatch Alarm for fraud volume spike detection
        # Using SQS queue depth as a proxy for flagged-transaction volume
        
        alarm_topic = sns.Topic(self, "FraudVolumeAlarmTopic")
        alarm_topic.add_subscription(
            subscriptions.EmailSubscription(os.environ["RECIPIENT_EMAIL"])
        )

        fraud_volume_alarm = cloudwatch.Alarm(
            self, "FraudVolumeSpike",
            metric=fraud_queue.metric_approximate_number_of_messages_visible(),
            threshold=5,
            evaluation_periods=1,
            alarm_description="Triggered when more than 5 flagged transactions are queued at once, suggesting a potential spike in fraud",
        )
        fraud_volume_alarm.add_alarm_action(cw_actions.SnsAction(alarm_topic))