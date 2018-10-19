![status stable](https://img.shields.io/badge/status-stable-green.svg)  

The **Netconf Collector** is a tool to collect information in Junos devices over Netconf.  
This tool was initially part of OpenNTI, the goal of this project is to create a standalone version.

> Features:
-  Supports Junos via Netconf and F5 Devices via iControl REST API
-  Scheduler support: Periodic data collection and dumping to influxdb via telegraf

# How to give it a try
You will need a running docker host and docker-compose to launch the test stack.

## 1- Define your devices parameters
Initialize `lab-xxx-hosts.yaml` & `lab-xxx-credentials.yaml` with the information corresponding to your device
Credentials and hosts file must be in "quickstart" folder. File starting with "lab" are .gitignored to prevent you from leaking sensible topology or security informations.

### Hosts files
File format will be :
```
device1:
  tags: [ junos, router ]
  address: 192.168.0.1
  context:
    - site: sitea
    - role: router

device2:
  tags: [ junos, switch ]
  address: 192.168.0.2
  context:
    - site: siteb
    - role: switch

device3:
  tags: [ junos ]
  address: 192.168.0.3
```

Keep in mind that `tags` are going to make the glue between hosts files, credentials and commands files.

### Credentials files
If you use ssh key based authentication, use this format :
```
lab_credentials:
    username: root
    method: key
    key_file: keys/private-key
    tags: juniper
```

If you use user and password, use this format :
```
lab_credentials:
    username: root
    password: <password>
    method: password
    key_file:
    tags: juniper
```

## 2- Launch the docker-compose stack

Pass the hosts, and credentials through ENV variables at the runtime so they keep safe

```
% CREDENTIALS=lab0-credentials.yaml HOSTS=lab0-hosts.yaml docker-compose up
```

## 3- Open Grafana  

Open a browser and go to http://0.0.0.0:3000, use "admin / admin " as login / password and you can start building nice dashboards.
