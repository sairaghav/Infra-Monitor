import sys,ctypes,os
import xml.etree.ElementTree as ET
import socket
import json
import time
from elasticsearch import Elasticsearch
from datetime import datetime
import base64

def send_to_es(host,port,index,data,es_user=None,es_pass=None,use_https=None,cert_verify=None):
    global cnt
    cnt += 1
    
    if use_https is not None and 'true' in use_https.lower():
        use_https = True
    else:
        use_https = False

    if cert_verify is not None and 'true' in cert_verify.lower():
        cert_verify = True
    else:
        cert_verify = False

    if use_https:
        if es_user is None and es_pass is None:
            es_host = 'https://'+host+':'+port
        else:
            es_host = 'https://'+es_user+':'+es_pass+'@'+host+':'+port
    else:
        if es_user is None and es_pass is None:
            es_host = 'http://'+host+':'+port
        else:
            es_host = 'http://'+es_user+':'+es_pass+'@'+host+':'+port

    id_val = base64.b64encode(str(time.time())+str(cnt))
    
    try:
        es = Elasticsearch(es_host,use_ssl=use_https,verify_certs=cert_verify)
        es.index(index=index,doc_type='monitor',id=id_val,body=data)
    except:
        print 'Elasticsearch not running or there is some error in the information provided'
        sys.exit()

def send_to_logstash(host,port,data):
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        sock.connect((host,int(port)))
    except:
        print 'Logstash pipeline not running or there is some error in the information provided'
        sys.exit()

    sock.send(json.dumps(data)+'\n')
    sock.close()
    
def monitor(input_xml):
    global cnt
    root = input_xml.getroot()

    output_type = root.get('output_type')
    output_host = root.get('output_host')
    output_port = root.get('output_port')

    if output_type == 'elasticsearch':
        index = root.get('index_name')
        index_name = index+'-'+time.strftime('%Y-%m-%d')

        es_user = root.get('es_user')
        es_pass = root.get('es_pass')
        use_https = root.get('use_https')
        cert_verify = root.get('cert_verify')
        cnt = 0

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
                    port = processes.get('port')

                    try:
                        sock_tcp = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                        sock_tcp.settimeout(2)
                        result_tcp = sock_tcp.connect_ex((host,int(port)))

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

                if no_of_processes == 0:
                    data = {'@timestamp':datetime.now().isoformat(),'environment':environment_name,'host':host,'tier':tier,'host_state':host_state,'host_status':host_status}

                    if output_type == 'elasticsearch':
                        send_to_es(es,index_name,data)
                    if output_type == 'logstash':
                        send_to_logstash(output_host,output_port,data)
            
if __name__ == '__main__':
    run = 1

    try:
        if os.geteuid() != 0:
            run = 0
    except AttributeError:
        if ctypes.windll.shell32.IsUserAnAdmin() == 0:
            run = 0

    if run == 1:
        try:
            input_xml = ET.parse(sys.argv[1])
            monitor(input_xml)
        except:
            print 'No input XML file given or there is some error in the information provided'
    else:
        print 'Run the program with admin/root privileges'

    sys.exit()
