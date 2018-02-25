import sys, ctypes
import xml.etree.ElementTree as ET
import socket
import json
import time
from elasticsearch import Elasticsearch
from datetime import datetime
import uuid

def send_to_es(host,port,index,data):
    try:
        es = Elasticsearch([{'host':host,'port':int(port)}])
    except:
        print 'Elasticsearch not running'
        sys.exit()

    es.index(index=index,doc_type='monitor',id=uuid.uuid4(),body=data)

def send_to_logstash(host,port,data):
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        sock.connect((host,int(port))
    except:
        print 'Logstash pipeline not running'
        sys.exit()

    sock.send(json.dumps(data)+'\n')
    sock.close()
    
def monitor(input_xml):
    root = input_xml.getroot()

    output_type = root.get('output_type')
    output_host = root.get('output_host')
    output_port = root.get('output_port')

    if output_type == 'elasticsearch':
        index = root.get('index_name')
        index_name = index+'-'+time.strftime('%Y-%m-%d')

    while(1):
        for environment in root:
            no_of_processes = 0
            environment_name = environment.get('environment_name')
            
            for hosts in environment:
                host = hosts.get('host_name')
                tier = hosts.get('tier')

                try:
                    sock_icmp = socket.socket(socket.AF_INET, socket.SOCK_RAW, socket.getprotobyname("icmp"))
                    sock_icmp.settimeout(2)
                    result_icmp = sock_icmp.sendto('',(socket.gethostbyname(host),0))

                    if result_icmp == 0:        
                        host_state = 1
                        host_status = "Up"
                    else:
                        host_state = 0
                        host_status = "Down"
                except:
                    host_state = 0
                    host_status = "Down"
                
                for processes in hosts:
                    no_of_processes += 1
                    process = processes.text
                    port = int(processes.get('port'))

                    try:
                        sock_tcp = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                        sock_tcp.settimeout(2)
                        result_tcp = sock_tcp.connect_ex((host,port))

                        if result_tcp == 0:
                            process_state = 1
                            process_status = "Running"
                        else:
                            process_state = 0
                            process_status = "Stopped"
                    except:
                        process_state = 0
                        process_status = "Stopped"

                    data = {'@timestamp':datetime.now().isoformat(),'environment':environment_name,'host':host,'tier':tier,'host_state':host_state,'host_status':host_status,'process_name':process,'process_state':process_state,'process_status':process_status}

                    if output_type == 'elasticsearch':
                        send_to_es(output_host,output_port,index_name,data)
                    if output_type == 'logstash':
                        send_to_logstash(output_host,output_port,data)
                    print data

                if no_of_processes == 0:
                    data = {'@timestamp':datetime.now().isoformat(),'environment':environment_name,'host':host,'tier':tier,'host_state':host_state,'host_status':host_status}

                    if output_type == 'elasticsearch':
                        send_to_es(output_host,output_port,index_name,data)
                    if output_type == 'logstash':
                        send_to_logstash(output_host,output_port,data)
                    print data
            
if ctypes.windll.shell32.IsUserAnAdmin() == 0:
    print '\nPlease run the program as Administrator'
else:
    try:
        input_xml = ET.parse(sys.argv[1])
        monitor(input_xml)
    except:
        print 'Please provide the input XML file'

sys.exit()
