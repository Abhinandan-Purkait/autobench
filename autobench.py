#!/usr/bin/env python3
import os.path

import click
import subprocess
import json

CONTEXT_SETTINGS = dict(help_option_names=['-h', '--help'])
RPC_DEFAULT_PATH = '/home/septimius/github.com/spdk/spdk/scripts/rpc.py'

@click.group(context_settings=CONTEXT_SETTINGS)
def cli():
    print("Storage Performance Benchmarking Tool")


@cli.command()
@click.option('-n', '--name', type=str, help='Name of the LVM LV', required=1)
@click.option('-v', '--volume-group', type=str, help='Name of the LVM VG', required=1)
@click.option('-d', '--disk', type=str, help='Device path of disk to be used', required=1)
@click.option('-s', '--size', type=str, help='Size of the device LV', required=1)
def create_lvm_stack(name, volume_group, disk, size):
    cmd = ['pvcreate', disk]
    cmd1 = ['vgcreate', volume_group, disk]
    cmd2 = ['lvcreate', '-n', name, volume_group, '--size', size]

    result = subprocess.run(cmd, capture_output=True)
    print(result.stdout)

    result = subprocess.run(cmd1, capture_output=True)
    print(result.stdout)

    result = subprocess.run(cmd2, capture_output=True)
    print(result.stdout)


@cli.command()
@click.option('-v', '--volume-group', type=str, help='Name of the LVM VG', required=1)
@click.option('-d', '--disk', type=str, help='Device path of disk to be wiped', required=1)
def remove_lvm_stack(volume_group, disk):
    cmd1 = ['vgremove', volume_group, '-f', '-y']
    cmd2 = ['pvremove', disk, '-f', '-y']

    result = subprocess.run(cmd1, capture_output=True)
    print(result.stdout)

    result = subprocess.run(cmd2, capture_output=True)
    print(result.stdout)


@cli.command()
@click.option('-v', '--volume-group', type=str, help='Name of the LVM VG', required=1)
@click.option('-n', '--lv-name', type=str, help='Device path of disk to be used', required=1)
@click.option('-i', '--ip-addr', type=str, help='Target\'s IP Address', required=1)
@click.option('-s', '--service-port', type=str, help='Target\'s Service Port', required=1)
def expose_lvm_stack(volume_group, lv_name, ip_addr, service_port):
    nqn = "nqn.2022-06.autobench."+volume_group+"."+lv_name
    parent_dir = '/sys/kernel/config/nvmet/subsystems/'
    path = os.path.join(parent_dir, nqn)
    os.mkdir(path)

    cmd = ['echo 1 | tee -a /sys/kernel/config/nvmet/subsystems/'+nqn+'/attr_allow_any_host']
    subprocess.call(cmd, shell=True)

    path = os.path.join(path.__str__(), 'namespaces/1')
    os.mkdir(path)

    cmd = ['echo -n /dev/'+volume_group+'/'+lv_name+' | tee -a /sys/kernel/config/nvmet/subsystems/'+nqn+'/namespaces/1/device_path']
    subprocess.call(cmd, shell=True)

    cmd = ['echo 1 | tee -a /sys/kernel/config/nvmet/subsystems/'+nqn+'/namespaces/1/enable']
    subprocess.call(cmd, shell=True)

    parent_dir = '/sys/kernel/config/nvmet/ports/'
    test_list = list(map(int, os.listdir(os.path.join(parent_dir, ''))))

    if len(test_list) == 0:
        path = os.path.join(parent_dir, '1')
        port_name = '1'
    else:
        test_list.sort()
        path = os.path.join(parent_dir, str(test_list.pop()+1))
        port_name = str(test_list.pop()+1)
    os.mkdir(path)

    cmd = ['echo '+ip_addr+'| tee -a /sys/kernel/config/nvmet/ports/'+port_name+'/addr_traddr']
    subprocess.call(cmd, shell=True)

    cmd = ['echo tcp | tee -a /sys/kernel/config/nvmet/ports/'+port_name+'/addr_trtype']
    subprocess.call(cmd, shell=True)

    cmd = ['echo '+service_port+'| tee -a /sys/kernel/config/nvmet/ports/'+port_name+'/addr_trsvcid']
    subprocess.call(cmd, shell=True)

    cmd = ['echo ipv4 | tee -a /sys/kernel/config/nvmet/ports/'+port_name+'/addr_adrfam']
    subprocess.call(cmd, shell=True)

    cmd = ['ln -s /sys/kernel/config/nvmet/subsystems/'+nqn+'/ /sys/kernel/config/nvmet/ports/'+port_name+'/subsystems/'+nqn]
    subprocess.call(cmd, shell=True)

    print('NQN: '+nqn)

@cli.command()
@click.option('-d', '--dev-paths', type=str, multiple=True, help='The Device Paths to be ran fio on', required=1)
@click.option('-r', '--runtime', type=str, help='Runtime of the FIO', default='20')
@click.option('-b', '--block-size', type=str, help='Block size to be used', default='512')
@click.option('-r', '--io-pattern', type=str, help='IO pattern of the fio', default='randrw')
@click.option('-s', '--size', type=str, help='Size to be written', default='800MB')
def run_performance_test(dev_paths, runtime, block_size, io_pattern, size):
    for x in dev_paths:
        cmd = ['fio', '--filename='+x, '--size='+size, '--direct=1', '--rw='+io_pattern, '--bs='+block_size, '--ioengine=libaio', '--iodepth=64', '--runtime='+runtime, '--numjobs=4', '--time_based', '--group_reporting', '--name=iops-test-job', '--eta-newline=1', '--output-format=json']
        output = subprocess.run(cmd, capture_output=True)
        x = json.loads(output.stdout)
        print(x["jobs"][0]["read"])



if __name__ == '__main__':
    cli()
