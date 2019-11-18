import boto3
import os, stat
from time import sleep
from random import randint

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

        self.used_private_ip = []

    def create_keypair(self,name):
        check_exists = self.check_key_pair(name)
        if check_exists:
            self.client.delete_key_pair(KeyName=name)
            print("\033[1;31;49mAPAGOU KEY PAIR\033[0;49;49m")

        response = self.client.create_key_pair(KeyName=name)

        try:
            os.chmod(name, stat.S_IWRITE)
        except Exception as e:
            print('\n\n',e,'\n\n')
            pass

        with open(name,'w') as private:
            private.write(response['KeyMaterial'])

        os.chmod(name, stat.S_IREAD)

        print("\033[1;32;49mCRIOU KEY PAIR\033[0;49;49m")

    def create_sec_group(self,name,desc,ports):
        check_exists = self.check_sec_group(name)

        while check_exists:
            try:
                self.client.delete_security_group(GroupName=name)
                sleep(1)
            except Exception as e:
                print('\n\n',e,'\n\n')
                pass
            check_exists = self.check_sec_group(name)
        print("\033[1;31;49mAPAGOU SECURITY GROUP\033[0;49;49m",name)

        response = self.client.create_security_group(Description=desc, GroupName=name)

        sleep(2)

        print("\033[1;32;49mCRIOU SECURITY GROUP\033[0;49;49m",name)

        self.liberate_port(name,ports)

        return response['GroupId']

    def liberate_port(self,name,ports):
        self.client.authorize_security_group_ingress(
            GroupName=name,
            IpPermissions=ports
        )

        print("\033[1;32;49mLIBEROU PORTAS SECURITY GROUP\033[0;49;49m")

    def check_sec_group(self,name):
        print('\033[1;33;49mVERIFICA EXISTENCIA SECURITY GROUP\033[0;49;49m',name)
        response = self.client.describe_security_groups()
        
        for i in response['SecurityGroups']:
            if i['GroupName'] == name:
                return (True)

    def check_key_pair(self,name):
        print('\033[1;33;49mVERIFICA EXISTENCIA KEY PAIR\033[0;49;49m')
        response = self.client.describe_key_pairs()
        
        for i in response['KeyPairs']:
            if i['KeyName'] == name:
                return (True)

    def create_instance(self,key_pair_name,sec_group_name,userData,imageID,privateAddress):
        print('\033[1;32;49mCRIANDO INSTÂNCIA\033[0;49;49m',sec_group_name)
        print('\033[1;36;49mISSO PODE LEVAR ALGUNS MINUTOS\033[0;49;49m')
        if not privateAddress == None:
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
                UserData=userData,
                PrivateIpAddress=privateAddress
            )
        else:
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

        waiter = self.client.get_waiter('instance_status_ok')
        waiter.wait(InstanceIds=[response['Instances'][0]['InstanceId']])

        return (response['Instances'][0]['InstanceId'])

    def delete_instances(self):
        instances_ids = self.get_instance_id()
        if len(instances_ids) > 0:
            instances_ids = self.instance_filter(instances_ids)

        try:    
            self.client.terminate_instances(
                InstanceIds=instances_ids
            )

            print('\033[1;31;49mTERMINANDO...\033[0;49;49m')
            waiter = self.client.get_waiter('instance_terminated')
            waiter.wait(InstanceIds=instances_ids)
        except Exception as e:
            pass

    def get_instance_id(self):
        print("\033[1;33;49mCHECANDO INSTÂNCIAS\033[0;49;49m")
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
        print('\033[1;33;49mCHECANDO STATUS\033[0;49;49m')
        response = self.client.describe_instance_status(
            InstanceIds=instances_ids,
            IncludeAllInstances=True
        )

        instances_ids = []
        for i in response['InstanceStatuses']:
            if(not i['InstanceState']['Name'] == 'terminated'):
                instances_ids.append(i['InstanceId'])

        return instances_ids

    def create_image(self,instance_id, image_name):
        print('\033[1;32;49mINICIALIZANDO\033[0;49;49m')
        waiter = self.client.get_waiter('instance_running')
        waiter.wait(InstanceIds=[instance_id])
        
        print('\033[1;33;49mAGUARDANDO STATUS OK\033[0;49;49m')
        waiter = self.client.get_waiter('instance_status_ok')
        waiter.wait(InstanceIds=[instance_id])

        print('\033[1;31;49mSTOPPING\033[0;49;49m')
        response = self.client.stop_instances(InstanceIds=[instance_id])

        waiter = self.client.get_waiter('instance_stopped')
        waiter.wait(InstanceIds=[instance_id])

        print('\033[1;32;49mCRIANDO IMAGEM\033[0;49;49m')
        response = self.client.create_image(
            InstanceId=instance_id,
            Name=image_name
        )

        waiter = self.client.get_waiter('image_available')
        waiter.wait(ImageIds=[response['ImageId']])

        self.client.terminate_instances(InstanceIds=[instance_id])

    def delete_image(self,img_name):
        print('\033[1;31;49mAPAGANDO IMAGENS\033[0;49;49m')
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
        except Exception as e:
            print('\n\n',e,'\n\n')
            pass

    def create_load_balancer(self,name,sec_inst_id):
        print('\033[1;32;49mCRIANDO LOAD BALANCER\033[0;49;49m')
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
            print('\033[1;31;49mDELETANDO LOAD BALANCER\033[0;49;49m')
            self.ldblcr.delete_load_balancer(LoadBalancerName=name)
        except Exception as e:
            print('\n\n',e,'\n\n')
            pass

    def create_l_config(self,name,img_name,key_p_name,sec_g_id):
        print('\033[1;32;49mCRIANDO LAUNCH CONFIGURATION\033[0;49;49m')
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
            print('\033[1;31;49mDELETANDO LAUNCH CONFIGURATION\033[0;49;49m')
            self.autoscale.delete_launch_configuration(LaunchConfigurationName=name)
        except Exception as e:
            print('\n\n',e,'\n\n')
            pass

    def create_auto_scaling(self,name,l_config_name,load_name):
        print('\033[1;32;49mCRIANDO AUTO SCALING GROUP\033[0;49;49m')
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
            print('\033[1;31;49mDELETANDO AUTO SCALING GROUP\033[0;49;49m')
            self.autoscale.delete_auto_scaling_group(
                AutoScalingGroupName=name,
                ForceDelete=True
            )

            while self.check_autoscalling(name):
                sleep(10)
        except Exception as e:
            print('\n\n',e,'\n\n')
            pass

    def check_autoscalling(self,name):
        print('\033[1;33;49mVERIFICA EXISTENCIA AUTOSCALLING GROUP\033[0;49;49m',name)
        response = self.autoscale.describe_auto_scaling_groups(
            AutoScalingGroupNames=[name]
        )
        return (not(len(response['AutoScalingGroups']) == 0))

    def create_elastic_ip(self):
        print('\033[1;32;49mCRIANDO ELASTIC IP\033[0;49;49m')
        response = self.client.allocate_address(Domain='vpc')
        
        self.client.create_tags(
            Resources=[
                response['AllocationId'],
            ],
            Tags=[
                {
                    'Key': 'Owner',
                    'Value': 'Andre'
                },
            ]
        )
        return(response['PublicIp'])
    
    def destroy_elastic_ip(self):
        print('\033[1;31;49mDELETANDO ELASTIC IP\033[0;49;49m')
        response = self.client.describe_addresses(
            Filters=[
                {
                    'Name': 'tag:Owner',
                    'Values': [
                        'Andre',
                    ]
                },
            ]
        )

        if not len(response['Addresses']) == 0:
            for i in response['Addresses']:
                response = self.client.release_address(
                    AllocationId=i['AllocationId']
                )

    def alocate_elastic_ip(self, pub_ip, inst_id):
        print('\033[1;32;49mALOCANDO INSTANCIA COM IP ELASTICO\033[0;49;49m')
        response = self.client.associate_address(
            InstanceId=inst_id,
            PublicIp=pub_ip,
            AllowReassociation=True
        )

    def get_thr_ocur(self,w_string,w_char,times):
        count = 0
        for i in range(len(w_string)):
            if w_string[i] == w_char:
                count += 1
                if count == times:
                    return i

    def get_local_fix_ip(self):
        print('\033[1;32;49mALOCANDO IP PRIVADO FIXO\033[0;49;49m')
        response = self.client.describe_vpcs()
        vpc_id = response['Vpcs'][0]['VpcId']

        response = self.client.describe_subnets(
            Filters=[
                {
                    'Name': 'vpc-id',
                    'Values': [
                        vpc_id,
                    ]
                },
            ],
        )

        cidr_vpc = response['Subnets'][0]['CidrBlock']
        sec_dot_place = self.get_thr_ocur(cidr_vpc,'.',3)
        new_fixed_ip = cidr_vpc[:sec_dot_place]+"."+str(randint(0,254))
        
        while new_fixed_ip in self.used_private_ip:
            new_fixed_ip = cidr_vpc[:sec_dot_place]+"."+str(randint(0,254))
        
        self.used_private_ip.append(new_fixed_ip)

        return new_fixed_ip

r1 = "us-east-1"
print("\n\nCOMECOU REGIÃO",r1)

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

key_pair_name = "key-pair-north-virginia"
sec_group_name = 'secgroup-instancia-deco'
img_name = 'P1 Deco'
load_name = 'LoadProjDeco'
launch_name = 'LaunchConfigDeco'
auto_name = 'AutoScaleDeco'

inst_ports = [{'FromPort': 22,'IpProtocol': 'tcp','IpRanges': [{'CidrIp': '0.0.0.0/0'},],'ToPort': 22},{'FromPort': 8080,'IpProtocol': 'tcp','IpRanges': [{'CidrIp': '0.0.0.0/0'},],'ToPort': 8080}]
load_ports = [{'FromPort': 80,'IpProtocol': 'tcp','IpRanges': [{'CidrIp': '0.0.0.0/0'},],'ToPort': 80}]
betweness_port = [{'FromPort': 0,'IpProtocol': 'tcp','IpRanges': [{'CidrIp': '0.0.0.0/0'},],'ToPort': 65000}]

northVirginia = AWS(r1)

northVirginia.destroy_elastic_ip()
# northVirginia.delete_auto_scaling(auto_name)
# northVirginia.delete_l_config(launch_name)
# northVirginia.delete_ld_balancer(load_name)
# northVirginia.delete_instances()
# northVirginia.delete_image(img_name)

betw_el_ip = northVirginia.create_elastic_ip()

# northVirginia.create_keypair(key_pair_name)

# sec_inst_id = northVirginia.create_sec_group(sec_group_name,'Security Group Instancia projeto',inst_ports)
# sec_load_id = northVirginia.create_sec_group('sec-group-load-deco','Security Group Load Balancer projeto',load_ports)
# sec_betwenn_id = northVirginia.create_sec_group('sec-group-betwenn-deco','Security Group para a instancia intermediaria',betweness_port)

# ins_id = northVirginia.create_instance(key_pair_name, sec_group_name,userData,'ami-07d0cf3af28718ef8',None)
# betwen_id = northVirginia.create_instance(key_pair_name, 'sec-group-betwenn-deco','','ami-07d0cf3af28718ef8',None)

# northVirginia.alocate_elastic_ip(betw_el_ip,betwen_id)

# northVirginia.create_image(ins_id,img_name)
# northVirginia.create_load_balancer(load_name,sec_load_id)
# northVirginia.create_l_config(launch_name,img_name,key_pair_name,[sec_inst_id])
# northVirginia.create_auto_scaling(auto_name,launch_name,[load_name])

print('FINALIZOU',r1)

##########REGIAO 2################REGIAO 2####################REGIAO 2################REGIAO 2#######

r2 = "us-east-2"
print("\n\nCOMECOU REGIÃO",r2)
ohio = AWS(r2)
private_ip_ws_ohio = ohio.get_local_fix_ip()
private_ip_db_ohio = ohio.get_local_fix_ip()
ohio.destroy_elastic_ip()
ohio.delete_instances()

#Fixo para todas as maquinas de Ohio
key_pair_name_ohio = 'key-pair-ohio'
inst_type_ohio = 'ami-0d5d9d301c853a04a' #t2.micro


#Especifico para a maquina de WebServer
open_port_ws = 8080
user_data_ws_ohio = '''#!/bin/bash
git clone https://github.com/decoejz/APS-cloud-comp.git
cd APS-cloud-comp

echo '{
    \"db_host\": \"'''+str(private_ip_db_ohio)+'''\",
    \"hostname\": \"0.0.0.0\",
    \"port\": '''+str(open_port_ws)+'''
}' >> /APS-cloud-comp/hosts.json
echo '{\"id\": 1}' >> /APS-cloud-comp/id.json
chmod 777 /APS-cloud-comp/id.json
chmod 777 /APS-cloud-comp/hosts.json
source comandos.sh
touch /etc/init.d/runWebServer.sh
echo '#!/bin/bash
python3 /APS-cloud-comp/webServer.py' >> /etc/init.d/runWebServer.sh
chmod 755 /etc/init.d/runWebServer.sh
echo '[Service]
ExecStart=/etc/init.d/runWebServer.sh

[Install]
WantedBy=default.target' >> /etc/systemd/system/runWebServer.service
systemctl enable runWebServer
reboot'''

sec_group_name_ws_ohio = 'web_server'
inst_ports_ws_ohio = [{'FromPort': open_port_ws,'IpProtocol': 'tcp','IpRanges': [{'CidrIp': betw_el_ip+'/32'},],'ToPort': open_port_ws}]

#Especifico para a maquina com o banco de dados
user_data_db_ohio = '''#!/bin/bash
wget -qO - https://www.mongodb.org/static/pgp/server-4.2.asc | sudo apt-key add -
echo "deb [ arch=amd64 ] https://repo.mongodb.org/apt/ubuntu bionic/mongodb-org/4.2 multiverse" | sudo tee /etc/apt/sources.list.d/mongodb-org-4.2.list
sudo apt-get update
sudo apt-get install -y mongodb-org

echo '# mongod.conf

# for documentation of all options, see:
#   http://docs.mongodb.org/manual/reference/configuration-options/

# Where and how to store data.
storage:
  dbPath: /var/lib/mongodb
  journal:
    enabled: true
#  engine:
#  mmapv1:
#  wiredTiger:

# where to write logging data.
systemLog:
  destination: file
  logAppend: true
  path: /var/log/mongodb/mongod.log

# network interfaces
net:
  port: 27017
  bindIp: 0.0.0.0

# how the process runs
processManagement:
  timeZoneInfo: /usr/share/zoneinfo

#security:

#operationProfiling:

#replication:

#sharding:

## Enterprise-Only Options:

#auditLog:

#snmp:' >> ~/temp.conf

cp ~/temp.conf /etc/mongod.conf
rm ~/temp.conf
systemctl enable mongod
reboot'''

sec_group_name_db_ohio = 'database'
inst_ports_db_ohio = [{'FromPort': 27017,'IpProtocol': 'tcp','IpRanges': [{'CidrIp': private_ip_ws_ohio+'/32'},],'ToPort': 27017}]

ohio.create_keypair(key_pair_name_ohio)
ws_elastic_ip = ohio.create_elastic_ip()
ohio.create_sec_group(sec_group_name_ws_ohio,'Security Group Instancia WS',inst_ports_ws_ohio)
ohio.create_sec_group(sec_group_name_db_ohio,'Security Group Instancia DB',inst_ports_db_ohio)

ws_inst_id = ohio.create_instance(key_pair_name_ohio, sec_group_name_ws_ohio,user_data_ws_ohio,inst_type_ohio,private_ip_ws_ohio)
ohio.alocate_elastic_ip(ws_elastic_ip,ws_inst_id)

db_inst_id = ohio.create_instance(key_pair_name_ohio, sec_group_name_db_ohio,user_data_db_ohio,inst_type_ohio,private_ip_db_ohio)

print('FINALIZOU',r2)
print("TERMINOU\n\n")