from aws_runner.cloud.boot import boot


def test_capacity_shortage_retries_in_same_zone(cloud, capacity_shortage):
    ec2, _, config = cloud
    allocate, sleep, original = capacity_shortage
    allocate.side_effect = [
        allocate.side_effect.__next__(),
        original(
            ImageId=config["ami"],
            MinCount=1,
            MaxCount=1,
            Placement={"AvailabilityZone": "us-east-1a"},
        ),
    ]
    instance = boot(ec2, config, [], "us-east-1a")
    assert instance["Placement"]["AvailabilityZone"] == "us-east-1a"
    assert allocate.call_count == 2
    assert all(
        call.kwargs["Placement"] == {"AvailabilityZone": "us-east-1a"}
        for call in allocate.call_args_list
    )
    sleep.assert_called_once_with(30)
