import boto3
import os, stat
from time import sleep

ACCESS_ID = os.environ.get("aws_access_key_id")
SECRET_KEY = os.environ.get("aws_secret_access_key")

class AWS():

    def __init__(self,region):
        self.client = boto3.client('ec2',
            aws_access_key_id=ACCESS_ID,
            aws_secret_access_key=SECRET_KEY,
            region_name=region)

        self.ldblcr = boto3.client('elb',
            aws_access_key_id=ACCESS_ID,
            aws_secret_access_key=SECRET_KEY,
            region_name=region)

        self.autoscale = boto3.client('autoscaling',
            aws_access_key_id=ACCESS_ID,
            aws_secret_access_key=SECRET_KEY,
            region_name=region)

    def create_keypair(self,name):
        check_exists = self.check_key_pair(name)
        if check_exists:
            self.client.delete_key_pair(KeyName=name)
            print("APAGOU KEY PAIR")

        response = self.client.create_key_pair(KeyName=name)

        try:
            os.chmod(name, stat.S_IWRITE)
        except:
            pass

        with open(name,'w') as private:
            private.write(response['KeyMaterial'])

        os.chmod(name, stat.S_IREAD)

        print("CRIOU KEY PAIR")

    def create_sec_group(self,name,desc,ports):
        check_exists = self.check_sec_group(name)

        while check_exists:
            try:
                self.client.delete_security_group(GroupName=name)
                sleep(1)
            except:
                pass
            check_exists = self.check_sec_group(name)
        print("APAGOU SECURITY GROUP")

        response = self.client.create_security_group(Description=desc, GroupName=name)

        print("CRIOU SECURITY GROUP")

        self.liberate_port(name,ports)

        return response['GroupId']

    def liberate_port(self,name,ports):
        self.client.authorize_security_group_ingress(
            GroupName=name,
            IpPermissions=ports
        )

        print("LIBEROU PORTAS SECURITY GROUP")

    def check_sec_group(self,name):
        print('VERIFICA EXISTENCIA SECURITY GROUP',name)
        response = self.client.describe_security_groups()
        
        for i in response['SecurityGroups']:
            if i['GroupName'] == name:
                return (True)

    def check_key_pair(self,name):
        print('VERIFICA EXISTENCIA KEY PAIR')
        response = self.client.describe_key_pairs()
        
        for i in response['KeyPairs']:
            if i['KeyName'] == name:
                return (True)

    def create_instance(self,key_pair_name,sec_group_name,userData,imageID):
        print('VAI CRIAR INSTÂNCIA')
        response = self.client.run_instances(
            InstanceType='t2.micro',
            ImageId=imageID,
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
            UserData=userData
        )
        return (response['Instances'][0]['InstanceId'])

    def delete_instances(self):
        instances_ids = self.get_instance_id()
        instances_ids = self.instance_filter(instances_ids)

        try:    
            self.client.terminate_instances(
                InstanceIds=instances_ids
            )

            print('TERMINANDO')
            waiter = self.client.get_waiter('instance_terminated')
            waiter.wait(InstanceIds=instances_ids)
        except:
            pass

    def get_instance_id(self):
        print("CHECANDO INSTÂNCIAS")
        response = self.client.describe_instances(
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

    def instance_filter(self,instances_ids):
        print('CHECANDO STATUS')
        response = self.client.describe_instance_status(
            Filters=[
                {
                    'Name': 'tag:Owner',
                    'Values': [
                        'Andre',
                    ]
                },
            ],
            InstanceIds=instances_ids,
            IncludeAllInstances=True
        )

        instances_ids = []
        for i in response['InstanceStatuses']:
            if(not i['InstanceState']['Name'] == 'terminated'):
                instances_ids.append(i['InstanceId'])

        return instances_ids

    def create_image(self,instance_id, image_name):
        print('INICIALIZANDO')
        waiter = self.client.get_waiter('instance_running')
        waiter.wait(InstanceIds=[instance_id])
        
        print('AGUARDANDO STATUS OK')
        waiter = self.client.get_waiter('instance_status_ok')
        waiter.wait(InstanceIds=[instance_id])

        print('STOPPING')
        response = self.client.stop_instances(InstanceIds=[instance_id])

        waiter = self.client.get_waiter('instance_stopped')
        waiter.wait(InstanceIds=[instance_id])

        print('CRIANDO IMAGEM')
        response = self.client.create_image(
            InstanceId=instance_id,
            Name=image_name
        )

        waiter = self.client.get_waiter('image_available')
        waiter.wait(ImageIds=[response['ImageId']])

        self.client.terminate_instances(InstanceIds=[instance_id])

    def delete_image(self,img_name):
        print('APAGANDO IMAGENS')
        response = self.client.describe_images(
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
            response = self.client.deregister_image(ImageId=img_id)
        except:
            pass

    def create_load_balancer(self,name,sec_inst_id):
        print('CRIANDO LOAD BALANCER')
        response = self.ldblcr.create_load_balancer(
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

    def delete_ld_balancer(self,name):
        try:
            print('DELETANDO LOAD BALANCER')
            self.ldblcr.delete_load_balancer(LoadBalancerName=name)
        except:
            pass

    def create_l_config(self,name,img_name,key_p_name,sec_g_id):
        print('CRIANDO LAUNCH CONFIGURATION')
        response = self.client.describe_images(
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

        self.autoscale.create_launch_configuration(
            LaunchConfigurationName=name,
            ImageId=img_id,
            KeyName=key_p_name,
            SecurityGroups=sec_g_id,
            InstanceType='t2.micro'
        )

    def delete_l_config(self,name):
        try:
            print('DELETANDO LAUNCH CONFIGURATION')
            self.autoscale.delete_launch_configuration(LaunchConfigurationName=name)
        except:
            pass

    def create_auto_scaling(self,name,l_config_name,load_name):
        print('CRIANDO AUTO SCALING GROUP')
        self.autoscale.create_auto_scaling_group(
            AutoScalingGroupName=name,
            LaunchConfigurationName=l_config_name,
            MinSize=1,
            MaxSize=5,
            AvailabilityZones=['us-east-1a','us-east-1b','us-east-1c','us-east-1d','us-east-1e','us-east-1f'],
            LoadBalancerNames=load_name
        )

    def delete_auto_scaling(self,name):
        try:
            print('DELETANDO AUTO SCALING GROUP')
            self.autoscale.delete_auto_scaling_group(
                AutoScalingGroupName=name,
                ForceDelete=True
            )

            while self.check_autoscalling(name):
                sleep(10)
        except:
            pass

    def check_autoscalling(self,name):
        print('VERIFICA EXISTENCIA AUTOSCALLING GROUP',name)
        response = self.autoscale.describe_auto_scaling_groups(
            AutoScalingGroupNames=[name]
        )
        return (not(len(response['AutoScalingGroups']) == 0))


userData = '''#!/bin/bash
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

key_pair_name = "keypair-projeto-deco"
sec_group_name = 'secgroup-instancia-deco'
img_name = 'P1 Deco'
load_name = 'LoadProjDeco'
launch_name = 'LaunchConfigDeco'
auto_name = 'AutoScaleDeco'

inst_ports = [{'FromPort': 22,'IpProtocol': 'tcp','IpRanges': [{'CidrIp': '0.0.0.0/0'},],'ToPort': 22},{'FromPort': 5000,'IpProtocol': 'tcp','IpRanges': [{'CidrIp': '0.0.0.0/0'},],'ToPort': 5000}]
load_ports = [{'FromPort': 80,'IpProtocol': 'tcp','IpRanges': [{'CidrIp': '0.0.0.0/0'},],'ToPort': 80}]

print("\n\nCOMECOU REGIÃO 1")

northVirginia = AWS("us-east-1")
northVirginia.delete_auto_scaling(auto_name)
northVirginia.delete_l_config(launch_name)
northVirginia.delete_ld_balancer(load_name)
northVirginia.delete_instances()
northVirginia.delete_image(img_name)
northVirginia.create_keypair(key_pair_name)
sec_inst_id = northVirginia.create_sec_group(sec_group_name,'Security Group Instancia projeto',inst_ports)
sec_load_id = northVirginia.create_sec_group('sec-group-load-deco','Security Group Load Balancer projeto',load_ports)
ins_id = northVirginia.create_instance(key_pair_name, sec_group_name,userData,'ami-07d0cf3af28718ef8')
northVirginia.create_image(ins_id,img_name)
northVirginia.create_load_balancer(load_name,sec_load_id)
northVirginia.create_l_config(launch_name,img_name,key_pair_name,[sec_inst_id])
northVirginia.create_auto_scaling(auto_name,launch_name,[load_name])


print("\n\nCOMECOU REGIÃO 2")

userData = '''#!/bin/bash
wget -qO - https://www.mongodb.org/static/pgp/server-4.2.asc | sudo apt-key add -
echo "deb [ arch=amd64 ] https://repo.mongodb.org/apt/ubuntu bionic/mongodb-org/4.2 multiverse" | sudo tee /etc/apt/sources.list.d/mongodb-org-4.2.list
sudo apt-get update
sudo apt-get install -y mongodb-org
sudo service mongod start
'''
sec_group_name = 'to_database'
inst_ports = [{'FromPort': 22,'IpProtocol': 'tcp','IpRanges': [{'CidrIp': '0.0.0.0/0'},],'ToPort': 22},{'FromPort': 5000,'IpProtocol': 'tcp','IpRanges': [{'CidrIp': '0.0.0.0/0'},],'ToPort': 5000}]
key_pair_name = 'key-pair-ohio'

ohio = AWS("us-east-2")

ohio.delete_instances()
ohio.create_keypair(key_pair_name)
sec_gr_inst_id = ohio.create_sec_group(sec_group_name,'Security Group Instancia DB',inst_ports)
ins_id = ohio.create_instance(key_pair_name, sec_group_name,userData,'ami-0d5d9d301c853a04a')

print("TERMINOU\n\n")