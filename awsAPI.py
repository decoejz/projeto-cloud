import boto3
import os, stat
from time import sleep

ACCESS_ID = os.environ.get("aws_access_key_id")
SECRET_KEY = os.environ.get("aws_secret_access_key")

client = boto3.client('ec2',
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

def create_sec_group(name,desc):
    check_exists = check_sec_group(name)

    if check_exists:
        client.delete_security_group(GroupName=name)
        print("APAGOU SECURITY GROUP")

    client.create_security_group(Description=desc, GroupName=name)

    print("CRIOU SECURITY GROUP")

    liberate_port(name)

def liberate_port(name):
    client.authorize_security_group_ingress(
        GroupName=name,
        IpPermissions=[
            {
                'FromPort': 22,
                'IpProtocol': 'tcp',
                'IpRanges': [
                    {
                        'CidrIp': '0.0.0.0/0'
                    },
                ],
                'ToPort': 22,
            },
            {
                'FromPort': 5000,
                'IpProtocol': 'tcp',
                'IpRanges': [
                    {
                        'CidrIp': '0.0.0.0/0'
                    },
                ],
                'ToPort': 5000,
            },
        ]
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
echo '#!bin/bash
python3 /APS-cloud-comp/webServer.py' >> /etc/init.d/runWebServer.sh
update-rc.d runWebServer.sh defaults
chmod 755 /etc/init.d/runWebServer.sh
reboot'''
    )

def delete_instance():
    instances_ids = check_instances()
    instances_ids = instance_filter(instances_ids)

    if (len(instances_ids)>0):
        print('VAI TERMINAR A INSTÂNCIA')
        client.terminate_instances(
            InstanceIds=instances_ids
        )

        terminated = len(instances_ids)
        while (terminated > 0):
            print('TERMINANDO')
            terminated = check_continue(instances_ids)
            sleep(2) #time in seconds


def check_instances():
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
    # print(response)
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

def check_continue(instances_ids):
    response = client.describe_instance_status(
        InstanceIds=instances_ids,
        IncludeAllInstances=True
    )

    terminated = 0
    for i in response['InstanceStatuses']:
        if(not i['InstanceState']['Name'] == 'terminated'):
            terminated += 1

    return terminated

# def check_status_ok()
#     response = client.describe_instance_status(
#         InstanceIds=instances_ids,
#         IncludeAllInstances=True
#     )

#     terminated = 0
#     for i in response['InstanceStatuses']:
#         if(not i['InstanceState']['Name'] == 'terminated'):
#             terminated += 1

#     return terminated


print("\n\nCOMECOU")

key_pair_name = "keypair-APS3-deco"
sec_group_name = 'secgroup-APS3-deco'

delete_instance()
create_keypair(key_pair_name)
create_sec_group(sec_group_name,'SecurityGroupAPS3 do deco')
create_instance(key_pair_name, sec_group_name)

print("TERMINOU\n\n")