def cleanup(ec2, instance, volume):
    ec2.terminate_instances(InstanceIds=[instance["InstanceId"]])
    ec2.get_waiter("instance_terminated").wait(InstanceIds=[instance["InstanceId"]])
    ec2.get_waiter("volume_available").wait(VolumeIds=[volume])
    ec2.delete_volume(VolumeId=volume)
