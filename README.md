![status experimental](https://img.shields.io/badge/status-experimental-yellow.svg)  

> **Development in progress**

The **Netconf Collector** is a tool to collect information in Junos devices over Netconf.  
This tool was initially part of OpenNTI, this goal of this project is to create a standalone version.


# How to give it a try

## 1- Define your devices parameters

Update `dev-01.yaml`, `dev-02.yaml` & `credentials.yaml` with the information corresponding to your device

## 2- Create container

```
make build
```

## 3- Start Containers

```
make telegraf
```
> for now, it assumes that an influxdb server is running on 172.17.0.2
