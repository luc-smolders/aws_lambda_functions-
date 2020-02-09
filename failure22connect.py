#!/bin/python3

import os
import boto3
import logging, gzip, re


class Failure22Connect:
    logging.basicConfig(filename="/home/ec2-user/logfiles.log",level=logging.INFO)

    def __init__(self):
        self.regex_pattern = re.compile("^\d{1}\s\d{12}\s(eni-[\S]+)\s([\d{1,3}\.]+)\s([\d{1,3}\.]+)\s(\d{1,4})[\s\S]+?([ACCEPT|REJECT]+)\s([OK]+)?")
        self.s3 = boto3.client('s3')
        self.ec2R = boto3.resource('ec2',region_name="us-east-1")
        self.ec2 = boto3.client('ec2',region_name="us-east-1")
        self.bucket_name = 'vpc-flowlog-dump'
        self.lf_path = '/home/ec2-user/lf/'
        self.console_log_directory = '/home/ec2-user/console_log/'
        self.main_logger = "/home/ec2-user/logfiles.log"
        if not os.path.exists(self.lf_path) and not os.path.exists(self.console_log_directory):
            os.mkdir(self.lf_path)
            os.mkdir(self.console_log_directory)
        if len(self.readLF()) == 0:
            self.pull_and_save_lf()
            self.uncompress_gzip()

    def rename_logfile(self,src,dest):
        #remove .gz extension on log file
        dest = src.rstrip(".log.gz") + '.log'
        os.rename(src,dest)

    def pull_and_save_lf(self):
        for lf in self.listAllLogFileS3():
            data, key = self.pull_logs_from_S3(lf)
            with open(self.lf_path + str(key), 'wb') as ink:
                ink.write(data)
                logging.info(str(lf))

    def uncompress_gzip(self):
        #decompress .gz logfile and rename
        for file in os.listdir(self.lf_path):
            if file.endswith('.gz'):
                file_binary = gzip.decompress(open(self.lf_path + file, 'rb').read())
                with open(self.lf_path + file, 'wb') as ink:
                    ink.write(file_binary)
                self.rename_logfile(self.lf_path + file,self.lf_path + file.rstrip(".log.gz") + '.log')

    def pull_logs_from_S3(self, lf):
        #return binary data and filename as tuple
        data = self.s3.get_object(Bucket=self.bucket_name, Key=lf)
        return (data['Body'].read(), lf.rsplit('/')[-1])

    def listAllLogFileS3(self):
        return  [k['Key'].strip() for k in self.s3.list_objects(Bucket=self.bucket_name)['Contents']]

    def parseLogFileS3(self):
        #parse log file, if SSH Reject message is detected, gather preliminary data
        for file in os.listdir(self.lf_path):
            if file.endswith('.log'):
                with open(self.lf_path + file) as logfile:
                    log_data = logfile.readlines()

            for line in log_data:
                try:
                    data = self.regex_pattern.match(line)
                    if data:
                        if data.group(4) == "22" and data.group(5) == "REJECT":
                            self.get_console_log(self.get_instance_id(data.group(3)))

                except Exception as e:
                    print(e)

    def get_instance_id(self,private_ip):
        return {info['Instances'][0]['PrivateIpAddress']: info['Instances'][0]['InstanceId'] for info in
                   self.ec2.describe_instances()['Reservations']}[private_ip]

    def get_console_log(self,instance_id):
        ec2instance = self.ec2R.Instance(instance_id)
        try:
            with open(f"{self.console_log_directory}{instance_id}.log", 'xt') as ink:
                ink.write(ec2instance.console_output()['Output'])
        except FileExistsError:
            pass

    def readLF(self):
        return open('logfiles.log').readlines()

    def pullOutstandingLF(self):
        #checks which logfiles have been pulled from s3, only download outstanding logfiles
        log_file_entries = set([entry.split(":")[2].strip() for entry in open(self.main_logger).readlines()])
        log_files_in_s3 = set(self.listAllLogFileS3())
        outstanding_files = log_files_in_s3 - log_file_entries
        for file in outstanding_files:
            data, key = self.pull_logs_from_S3(file)
            with open(self.lf_path + str(key), 'wb') as ink:
                ink.write(data)
                logging.info(str(key))
        self.uncompress_gzip()
        self.parseLogFileS3()

if __name__ == "__main__":
    test = Failure22Connect()
    test.pullOutstandingLF()


#AWS S3 EC2 VPC Flowlog practice
#Fetch console logs from instance when SSH connection failure detected in VPC flow logs
#Elliott Arnold 2-9-20
#WIP


#AWS #VPC #EC2 #S3 practice:

#I had a small idea I ran across Michael Zuniga & Luis Plascencia this week, I wanted to detect #ssh connection failures to #EC2 instances and preform some preliminary #automation for investigation. The recommendation was enable VPC flow logs. I managed to put together a #quickAndDirty proof of concept that uses an administrative EC2 node to periodically pull VPC flow logs from an S3 bucket. The log files are subsequently decompressed and parsed; If SSH connection failures are detected, the instance console logs are fetched and stored locally as a preliminary action.

#875

#practice #pythonic #scripting #linux #systemAdministration #cloudComputing #investigations #boto3