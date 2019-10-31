import boto3
import os, stat
from time import sleep

print("\n\nCOMECOU")

ACCESS_ID = os.environ.get("aws_access_key_id")
SECRET_KEY = os.environ.get("aws_secret_access_key")

client = boto3.client('ec2',
    aws_access_key_id=ACCESS_ID,
    aws_secret_access_key=SECRET_KEY,
    region_name="us-east-1")

ldblcr = boto3.client('elb',
    aws_access_key_id=ACCESS_ID,
    aws_secret_access_key=SECRET_KEY,
    region_name="us-east-1")

autoscale = boto3.client('autoscaling',
    aws_access_key_id=ACCESS_ID,
    aws_secret_access_key=SECRET_KEY,
    region_name="us-east-1")

def create_keypair(name):
    check_exists = check_key_pair(name)
    if check_exists:
        client.delete_key_pair(KeyName=name)
        print("APAGOU KEY PAIR")

    response = client.create_key_pair(KeyName=name)

    try:
        os.chmod(name, stat.S_IWRITE)
    except:
        pass

    with open(name,'w') as private:
        private.write(response['KeyMaterial'])

    os.chmod(name, stat.S_IREAD)

    print("CRIOU KEY PAIR")

def create_sec_group(name,desc,ports):
    check_exists = check_sec_group(name)

    if check_exists:
        try:
            client.delete_security_group(GroupName=name)
        except:
            pass
        print("APAGOU SECURITY GROUP")

    response = client.create_security_group(Description=desc, GroupName=name)

    print("CRIOU SECURITY GROUP")

    liberate_port(name,ports)

    return response['GroupId']

def liberate_port(name,ports):
    client.authorize_security_group_ingress(
        GroupName=name,
        IpPermissions=ports
    )

    print("LIBEROU PORTAS SECURITY GROUP")

def check_sec_group(name):
    print('VERIFICA EXISTENCIA SECURITY GROUP')
    response = client.describe_security_groups()
    
    for i in response['SecurityGroups']:
        if i['GroupName'] == name:
            return (True)

def check_key_pair(name):
    print('VERIFICA EXISTENCIA KEY PAIR')
    response = client.describe_key_pairs()
    
    for i in response['KeyPairs']:
        if i['KeyName'] == name:
            return (True)

def create_instance(key_pair_name,sec_group_name):
    print('VAI CRIAR INSTÂNCIA')
    response = client.run_instances(
        InstanceType='t2.micro',
        ImageId='ami-07d0cf3af28718ef8',
        KeyName=key_pair_name,
        MaxCount=1,
        MinCount=1,
        SecurityGroups=[
            sec_group_name
        ],
        TagSpecifications=[
            {
                'ResourceType': 'instance',
                'Tags': [
                    {
                        'Key': 'Owner',
                        'Value': 'Andre'
                    },
                ]
            },
        ],
        UserData='''#!/bin/bash
git clone https://github.com/decoejz/APS-cloud-comp.git
cd APS-cloud-comp
source comandos.sh
touch /etc/init.d/runWebServer.sh
echo '#!/bin/bash
python3 /APS-cloud-comp/webServer.py' >> /etc/init.d/runWebServer.sh
chmod 755 /etc/init.d/runWebServer.sh
echo '
[Service]
ExecStart=/etc/init.d/runWebServer.sh

[Install]
WantedBy=default.target' >> /etc/systemd/system/runWebServer.service
systemctl enable runWebServer
reboot'''
    )
    return (response['Instances'][0]['InstanceId'])

def delete_instances():
    instances_ids = get_instance_id()
    instances_ids = instance_filter(instances_ids)

    try:    
        client.terminate_instances(
            InstanceIds=instances_ids
        )

        print('TERMINANDO')
        waiter = client.get_waiter('instance_terminated')
        waiter.wait(InstanceIds=instances_ids)
    except:
        pass

def get_instance_id():
    print("CHECANDO INSTÂNCIAS")
    response = client.describe_instances(
        Filters=[
            {
                'Name': 'tag:Owner',
                'Values': [
                    'Andre',
                ]
            },
        ]
    )

    instances_ids = []
    for i in response['Reservations']:
        instances_ids.append(i['Instances'][0]['InstanceId'])

    return instances_ids

def instance_filter(instances_ids):
    print('CHECANDO STATUS')
    response = client.describe_instance_status(
        InstanceIds=instances_ids,
        IncludeAllInstances=True
    )

    instances_ids = []
    for i in response['InstanceStatuses']:
        if(not i['InstanceState']['Name'] == 'terminated'):
            instances_ids.append(i['InstanceId'])

    return instances_ids

def create_image(instance_id, image_name):
    print('INICIALIZANDO')
    waiter = client.get_waiter('instance_running')
    waiter.wait(InstanceIds=[instance_id])
    
    print('AGUARDANDO STATUS OK')
    waiter = client.get_waiter('instance_status_ok')
    waiter.wait(InstanceIds=[instance_id])

    print('STOPPING')
    response = client.stop_instances(InstanceIds=[instance_id])

    waiter = client.get_waiter('instance_stopped')
    waiter.wait(InstanceIds=[instance_id])

    print('CRIANDO IMAGEM')
    response = client.create_image(
        InstanceId=instance_id,
        Name=image_name
    )

    waiter = client.get_waiter('image_available')
    waiter.wait(ImageIds=[response['ImageId']])

    client.terminate_instances(InstanceIds=[instance_id])

def delete_image(img_name):
    print('APAGANDO IMAGENS')
    response = client.describe_images(
        Filters=[
        {
            'Name': 'name',
            'Values': [
                img_name,
            ]
        },
    ]
    )

    try:
        img_id = response['Images'][0]['ImageId']
        response = client.deregister_image(ImageId=img_id)
    except:
        pass

def create_load_balancer(name,sec_inst_id):
    print('CRIANDO LOAD BALANCER')
    response = ldblcr.create_load_balancer(
        LoadBalancerName=name,
        Listeners=[{
            'Protocol': 'HTTP',
            'LoadBalancerPort': 80,
            'InstancePort': 5000
        }],
        AvailabilityZones=['us-east-1a','us-east-1b','us-east-1c','us-east-1d','us-east-1e','us-east-1f'],
        SecurityGroups=[sec_inst_id],
        Tags=[
        {
            'Key': 'name',
            'Value': 'DecoLB'
        },
    ]
    )

def delete_ld_balancer(name):
    try:
        print('DELETANDO LOAD BALANCER')
        ldblcr.delete_load_balancer(LoadBalancerName=name)
    except:
        pass

def create_l_config(name,img_name,key_p_name,sec_g_id):
    print('CRIANDO LAUNCH CONFIGURATION')
    response = client.describe_images(
        Filters=[
        {
            'Name': 'name',
            'Values': [
                img_name,
            ]
        },
    ]
    )
    img_id = response['Images'][0]['ImageId']

    autoscale.create_launch_configuration(
        LaunchConfigurationName=name,
        ImageId=img_id,
        KeyName=key_p_name,
        SecurityGroups=sec_g_id,
        InstanceType='t2.micro'
    )

def delete_l_config(name):
    try:
        print('DELETANDO LAUNCH CONFIGURATION')
        autoscale.delete_launch_configuration(LaunchConfigurationName=name)
    except:
        pass

def create_auto_scaling(name,l_config_name,load_name):
    print('CRIANDO AUTO SCALING GROUP')
    autoscale.create_auto_scaling_group(
        AutoScalingGroupName=name,
        LaunchConfigurationName=l_config_name,
        MinSize=1,
        MaxSize=5,
        AvailabilityZones=['us-east-1a','us-east-1b','us-east-1c','us-east-1d','us-east-1e','us-east-1f'],
        LoadBalancerNames=load_name
    )

def delete_auto_scaling(name):
    try:
        print('DELETANDO AUTO SCALING GROUP')
        autoscale.delete_auto_scaling_group(
            AutoScalingGroupName=name,
            ForceDelete=True
        )
    except:
        pass

key_pair_name = "keypair-APS3-deco"
sec_group_name = 'secgroup-APS3-deco'
img_name = 'P1 Deco'
load_name = 'LoadProjDeco'
launch_name = 'LaunchConfigDeco'
auto_name = 'AutoScaleDeco'

inst_ports = [{'FromPort': 22,'IpProtocol': 'tcp','IpRanges': [{'CidrIp': '0.0.0.0/0'},],'ToPort': 22},{'FromPort': 5000,'IpProtocol': 'tcp','IpRanges': [{'CidrIp': '0.0.0.0/0'},],'ToPort': 5000}]
load_ports = [{'FromPort': 80,'IpProtocol': 'tcp','IpRanges': [{'CidrIp': '0.0.0.0/0'},],'ToPort': 80}]

delete_auto_scaling(auto_name)
delete_l_config(launch_name)
delete_ld_balancer(load_name)
delete_instances()
delete_image(img_name)
create_keypair(key_pair_name)
sec_inst_id = create_sec_group(sec_group_name,'Security Group Instancia projeto',inst_ports)
sec_load_id = create_sec_group('sec-group-load-deco','Security Group Load Balancer projeto',load_ports)
ins_id = create_instance(key_pair_name, sec_group_name)
create_image(ins_id,img_name)
create_load_balancer(load_name,sec_load_id)
create_l_config(launch_name,img_name,key_pair_name,[sec_inst_id])
create_auto_scaling(auto_name,launch_name,[load_name])

print("TERMINOU\n\n")