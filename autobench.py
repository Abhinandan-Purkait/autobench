#!/usr/bin/env python3
import os.path

import click
import subprocess
import json
import math

CONTEXT_SETTINGS = dict(help_option_names=['-h', '--help'])
RPC_DEFAULT_PATH = '/home/septimius/github.com/spdk/spdk/scripts/rpc.py'


@click.group(context_settings=CONTEXT_SETTINGS)
def cli():
    print("Storage Performance Benchmarking Tool")


def convert(unit):
    num = [s for s in unit if s.isdigit()]
    unit_str = [s for s in unit if not s.isdigit()]
    sizes = {'Gi': 1, 'Ti': 2}
    return int(int("".join(num)) * math.pow(1024, sizes["".join(unit_str)]))


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
    nqn = "nqn.2022-06.autobench." + volume_group + "." + lv_name
    parent_dir = '/sys/kernel/config/nvmet/subsystems/'
    path = os.path.join(parent_dir, nqn)
    os.mkdir(path)

    cmd = ['echo 1 | tee -a /sys/kernel/config/nvmet/subsystems/' + nqn + '/attr_allow_any_host']
    subprocess.call(cmd, shell=True)

    path = os.path.join(path.__str__(), 'namespaces/1')
    os.mkdir(path)

    cmd = [
        'echo -n /dev/' + volume_group + '/' + lv_name + ' | tee -a /sys/kernel/config/nvmet/subsystems/' + nqn + '/namespaces/1/device_path']
    subprocess.call(cmd, shell=True)

    cmd = ['echo 1 | tee -a /sys/kernel/config/nvmet/subsystems/' + nqn + '/namespaces/1/enable']
    subprocess.call(cmd, shell=True)

    parent_dir = '/sys/kernel/config/nvmet/ports/'
    test_list = list(map(int, os.listdir(os.path.join(parent_dir, ''))))

    if len(test_list) == 0:
        path = os.path.join(parent_dir, '1')
        port_name = '1'
    else:
        test_list.sort()
        path = os.path.join(parent_dir, str(test_list.pop() + 1))
        port_name = str(test_list.pop() + 1)
    os.mkdir(path)

    cmd = ['echo ' + ip_addr + '| tee -a /sys/kernel/config/nvmet/ports/' + port_name + '/addr_traddr']
    subprocess.call(cmd, shell=True)

    cmd = ['echo tcp | tee -a /sys/kernel/config/nvmet/ports/' + port_name + '/addr_trtype']
    subprocess.call(cmd, shell=True)

    cmd = ['echo ' + service_port + '| tee -a /sys/kernel/config/nvmet/ports/' + port_name + '/addr_trsvcid']
    subprocess.call(cmd, shell=True)

    cmd = ['echo ipv4 | tee -a /sys/kernel/config/nvmet/ports/' + port_name + '/addr_adrfam']
    subprocess.call(cmd, shell=True)

    cmd = [
        'ln -s /sys/kernel/config/nvmet/subsystems/' + nqn + '/ /sys/kernel/config/nvmet/ports/' + port_name + '/subsystems/' + nqn]
    subprocess.call(cmd, shell=True)

    print('NQN: ' + nqn)


@cli.command()
@click.option('-d', '--dev-paths', type=str, multiple=True, help='The Device Paths to be ran fio on', required=1)
@click.option('-r', '--runtime', type=str, help='Runtime of the FIO', default='20')
@click.option('-b', '--block-size', type=str, help='Block size to be used', default='512')
@click.option('-r', '--io-pattern', type=str, help='IO pattern of the fio', default='randrw')
@click.option('-s', '--size', type=str, help='Size to be written', default='800MB')
def run_performance_test(dev_paths, runtime, block_size, io_pattern, size):
    for x in dev_paths:
        cmd = ['fio', '--filename=' + x, '--size=' + size, '--direct=1', '--rw=' + io_pattern, '--bs=' + block_size,
               '--ioengine=libaio', '--iodepth=64', '--runtime=' + runtime, '--numjobs=4', '--time_based',
               '--group_reporting', '--name=iops-test-job', '--eta-newline=1', '--output-format=json']
        output = subprocess.run(cmd, capture_output=True)
        x = json.loads(output.stdout)
        print(x["jobs"][0]["read"])


@cli.command()
@click.option('-n', '--lvol-name', type=str, help='Name of the SPDK Logical Volume', required=1)
@click.option('-v', '--pool-name', type=str, help='Name of the SPDK POOL', required=1)
@click.option('-d', '--disk', type=str, help='Device path of disk to be used', required=1)
@click.option('-s', '--size', type=str, help='Size of the Logical Volume', required=1)
def create_spdk_stack(lvol_name, pool_name, disk, size):
    cmd = [RPC_DEFAULT_PATH, 'bdev_aio_create', disk, lvol_name + pool_name]
    cmd1 = [RPC_DEFAULT_PATH, 'bdev_lvol_create_lvstore', lvol_name + pool_name, pool_name]
    cmd2 = [RPC_DEFAULT_PATH, 'bdev_lvol_create', lvol_name, str(convert(size)), '-l', pool_name]

    subprocess.run(cmd, capture_output=True)
    subprocess.run(cmd1, capture_output=True)
    x=subprocess.run(cmd2)
    print(x)
    print("Created spdk stack")


@cli.command()
@click.option('-n', '--lvol-name', type=str, help='Name of the SPDK Logical Volume', required=1)
@click.option('-v', '--pool-name', type=str, help='Name of the SPDK POOL', required=1)
def remove_spdk_stack(lvol_name, pool_name):
    cmd = [RPC_DEFAULT_PATH, 'bdev_lvol_delete', lvol_name]
    cmd1 = [RPC_DEFAULT_PATH, 'bdev_lvol_delete_lvstore', pool_name]
    cmd2 = [RPC_DEFAULT_PATH, 'bdev_aio_delete', lvol_name + pool_name]
    subprocess.run(cmd, capture_output=True)
    subprocess.run(cmd1, capture_output=True)
    subprocess.run(cmd2, capture_output=True)
    print("Removed spdk stack")


@cli.command()
@click.option('-p', '--pool-name', type=str, help='Name of the spdk pool', required=1)
@click.option('-n', '--lvol-name', type=str, help='Device path of disk to be used', required=1)
@click.option('-i', '--ip-addr', type=str, help='Target\'s IP Address', required=1)
@click.option('-s', '--service-port', type=str, help='Target\'s Service Port', required=1)
def expose_spdk_stack(pool_name, lvol_name, ip_addr, service_port):
    nqn = "nqn.2022-06.autobench.spdk:" + lvol_name
    cmd = [RPC_DEFAULT_PATH, 'nvmf_create_transport', '-tTCP', '-u 16384', '-m 8', '-c 8192']
    cmd1 = [RPC_DEFAULT_PATH, 'nvmf_create_subsystem', nqn, '-a', '-s', lvol_name+'001', '-d', 'autobech_spdk']
    cmd2 = [RPC_DEFAULT_PATH, 'nvmf_subsystem_add_ns', nqn, pool_name+'/'+lvol_name]
    cmd3 = [RPC_DEFAULT_PATH, 'nvmf_subsystem_add_listener', nqn, '-t', 'tcp', '-a', ip_addr, '-s', service_port]

    subprocess.run(cmd)
    subprocess.run(cmd1)
    subprocess.run(cmd2)
    subprocess.run(cmd3)
    print(nqn)


if __name__ == '__main__':
    cli()
