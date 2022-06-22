#!/usr/bin/env python3
import os.path

import click
import subprocess
import json
import math
import numpy as np
import matplotlib.pyplot as plt

CONTEXT_SETTINGS = dict(help_option_names=['-h', '--help'])
RPC_DEFAULT_PATH = '/home/septimius/github.com/spdk/spdk/scripts/rpc.py'


@click.group(context_settings=CONTEXT_SETTINGS)
def cli():
    """AutoBench is a tool that can automate deployment of storage stacks
       and can expose these stacks over nvme fabrics and provide a way to
       compare the storage stacks by storage performance benchmarking.
    """


def convert(unit):
    num = [s for s in unit if s.isdigit()]
    unit_str = [s for s in unit if not s.isdigit()]
    sizes = {'Gi': 1, 'Ti': 2}
    return int(int("".join(num)) * math.pow(1024, sizes["".join(unit_str)]))


def make_graph(min_ops, max_ops, mean_ops, ticks, name, header, unit):
    barWidth = 0.25
    fig = plt.subplots(figsize=(12, 8))

    br1 = np.arange(len(min_ops))
    br2 = [x + barWidth for x in br1]
    br3 = [x + barWidth for x in br2]

    plt.bar(br1, min_ops, color='r', width=barWidth,
            edgecolor='grey', label='MIN IOPS')
    plt.bar(br2, max_ops, color='g', width=barWidth,
            edgecolor='grey', label='MAX IOPS')
    plt.bar(br3, mean_ops, color='b', width=barWidth,
            edgecolor='grey', label='MEAN IOPS')

    plt.xlabel(header, fontweight='bold', fontsize=15)
    plt.ylabel(unit, fontweight='bold', fontsize=15)
    plt.xticks([r + barWidth for r in range(len(min_ops))],
               ticks)

    plt.legend()
    plt.savefig('/tmp/'+name)


@cli.command()
@click.option('-n', '--name', type=str, help='Name of the LVM LV', required=1)
@click.option('-v', '--volume-group', type=str, help='Name of the LVM VG', required=1)
@click.option('-d', '--disk', type=str, help='Device path of disk to be used', required=1)
@click.option('-s', '--size', type=str, help='Size of the device LV', required=1)
def create_lvm_stack(name, volume_group, disk, size):
    """Create LVM Stack would deploy the whole LVM stack, i.e create a
       LVM PV and then a LVM VG on top of it and finally a LVM LV.
    """
    cmd = ['pvcreate', disk]
    cmd1 = ['vgcreate', volume_group, disk]
    cmd2 = ['lvcreate', '-n', name, volume_group, '--size', size]

    subprocess.run(cmd, capture_output=True)
    subprocess.run(cmd1, capture_output=True)
    subprocess.run(cmd2, capture_output=True)
    print("Created LVM stack")


@cli.command()
@click.option('-v', '--volume-group', type=str, help='Name of the LVM VG', required=1)
@click.option('-d', '--disk', type=str, help='Device path of disk to be wiped', required=1)
def remove_lvm_stack(volume_group, disk):
    """Remove LVM Stack would remove the whole deployed LVM stack.
    """
    cmd1 = ['vgremove', volume_group, '-f', '-y']
    cmd2 = ['pvremove', disk, '-f', '-y']

    subprocess.run(cmd1, capture_output=True)
    subprocess.run(cmd2, capture_output=True)
    print("Removed LVM stack")


@cli.command()
@click.option('-v', '--volume-group', type=str, help='Name of the LVM VG', required=1)
@click.option('-n', '--lv-name', type=str, help='Device path of disk to be used', required=1)
@click.option('-i', '--ip-addr', type=str, help='Target\'s IP Address', required=1)
@click.option('-s', '--service-port', type=str, help='Target\'s Service Port', required=1)
def expose_lvm_stack(volume_group, lv_name, ip_addr, service_port):
    """Expose LVM stack would expose the LVM volume over nvme fabrics on the provided
    IP address, and Service Port. This will return the nqn which can be used to connect
    over nvme on TCP protocol.
    """
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
    """Run Performance test would run a performance comparison on the provided nvme exposed dev paths, or any filesystem
    path. This would generate a graph which can be used for a visual comparision.
    """
    min_r_ops = []
    max_r_ops = []
    mean_r_ops = []

    min_r_lat = []
    max_r_lat = []
    mean_r_lat = []

    min_r_slat = []
    max_r_slat = []
    mean_r_slat = []

    min_r_clat = []
    max_r_clat = []
    mean_r_clat = []

    min_w_ops = []
    max_w_ops = []
    mean_w_ops = []

    min_w_lat = []
    max_w_lat = []
    mean_w_lat = []

    min_w_slat = []
    max_w_slat = []
    mean_w_slat = []

    min_w_clat = []
    max_w_clat = []
    mean_w_clat = []

    ticks = []
    y = 1
    for x in dev_paths:
        cmd = ['fio', '--filename=' + x, '--size=' + size, '--direct=1', '--rw=' + io_pattern, '--bs=' + block_size,
               '--ioengine=libaio', '--iodepth=64', '--runtime=' + runtime, '--numjobs=4', '--time_based',
               '--group_reporting', '--name=iops-test-job', '--eta-newline=1', '--output-format=json']

        output = subprocess.run(cmd, capture_output=True)
        x = json.loads(output.stdout)

        min_r_ops.append(x["jobs"][0]["read"]["iops_min"])
        max_r_ops.append(x["jobs"][0]["read"]["iops_max"])
        mean_r_ops.append(x["jobs"][0]["read"]["iops_mean"])

        min_r_slat.append(x["jobs"][0]["read"]["slat_ns"]["min"])
        max_r_slat.append(x["jobs"][0]["read"]["slat_ns"]["max"])
        mean_r_slat.append(x["jobs"][0]["read"]["slat_ns"]["mean"])

        min_r_clat.append(x["jobs"][0]["read"]["clat_ns"]["min"])
        max_r_clat.append(x["jobs"][0]["read"]["clat_ns"]["max"])
        mean_r_clat.append(x["jobs"][0]["read"]["clat_ns"]["mean"])

        min_r_lat.append(x["jobs"][0]["read"]["lat_ns"]["min"])
        max_r_lat.append(x["jobs"][0]["read"]["lat_ns"]["max"])
        mean_r_lat.append(x["jobs"][0]["read"]["lat_ns"]["mean"])

        min_w_ops.append(x["jobs"][0]["write"]["iops_min"])
        max_w_ops.append(x["jobs"][0]["write"]["iops_max"])
        mean_w_ops.append(x["jobs"][0]["write"]["iops_mean"])

        min_w_slat.append(x["jobs"][0]["write"]["slat_ns"]["min"])
        max_w_slat.append(x["jobs"][0]["write"]["slat_ns"]["max"])
        mean_w_slat.append(x["jobs"][0]["write"]["slat_ns"]["mean"])

        min_w_clat.append(x["jobs"][0]["write"]["clat_ns"]["min"])
        max_w_clat.append(x["jobs"][0]["write"]["clat_ns"]["max"])
        mean_w_clat.append(x["jobs"][0]["write"]["clat_ns"]["mean"])

        min_w_lat.append(x["jobs"][0]["write"]["lat_ns"]["min"])
        max_w_lat.append(x["jobs"][0]["write"]["lat_ns"]["max"])
        mean_w_lat.append(x["jobs"][0]["write"]["lat_ns"]["mean"])

        ticks.append(x["disk_util"][0]["name"])

    make_graph(min_r_ops, max_r_ops, mean_r_ops, ticks, "read.png", "READ IOPS", "Inout/Output per second")
    make_graph(min_r_slat, min_r_slat, min_r_slat, ticks, "rslat.png", "READ SUBMISSION LATENCY", "nanosecond")
    make_graph(min_r_clat, min_r_clat, min_r_clat, ticks, "rclat.png", "READ COMPLETION LATENCY", "nanosecond")
    make_graph(min_r_lat, min_r_lat, min_r_lat, ticks, "rlat.png", "READ TOTAL LATENCY", "nanosecond")

    make_graph(min_w_ops, max_w_ops, mean_w_ops, ticks, "write.png", "WRITE IOPS", "Inout/Output per second")
    make_graph(min_w_slat, min_w_slat, min_w_slat, ticks, "wslat.png", "WRITE SUBMISSION LATENCY", "nanosecond")
    make_graph(min_w_clat, min_w_clat, min_w_clat, ticks, "wclat.png", "WRITE COMPLETION LATENCY", "nanosecond")
    make_graph(min_w_lat, min_w_lat, min_w_lat, ticks, "wlat.png", "WRITE TOTAL LATENCY", "nanosecond")


@cli.command()
@click.option('-n', '--lvol-name', type=str, help='Name of the SPDK Logical Volume', required=1)
@click.option('-v', '--pool-name', type=str, help='Name of the SPDK POOL', required=1)
@click.option('-d', '--disk', type=str, help='Device path of disk to be used', required=1)
@click.option('-s', '--size', type=str, help='Size of the Logical Volume', required=1)
def create_spdk_stack(lvol_name, pool_name, disk, size):
    """Create SPDK Stack would deploy the whole SPDK stack, i.e create a
       spdk bdev and then a spdk lvolstore on top of it and finally a spdk lvol.
    """
    cmd = [RPC_DEFAULT_PATH, 'bdev_aio_create', disk, lvol_name + pool_name]
    cmd1 = [RPC_DEFAULT_PATH, 'bdev_lvol_create_lvstore', lvol_name + pool_name, pool_name]
    cmd2 = [RPC_DEFAULT_PATH, 'bdev_lvol_create', lvol_name, str(convert(size)), '-l', pool_name]

    subprocess.run(cmd, capture_output=True)
    subprocess.run(cmd1, capture_output=True)
    subprocess.run(cmd2)
    print("Created spdk stack")


@cli.command()
@click.option('-n', '--lvol-name', type=str, help='Name of the SPDK Logical Volume', required=1)
@click.option('-v', '--pool-name', type=str, help='Name of the SPDK POOL', required=1)
def remove_spdk_stack(lvol_name, pool_name):
    """Remove SPDK Stack would remove the whole deployed LVM stack.
    """
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
    """Expose SPDK stack would expose the SPDK lvol over nvme fabrics on the provided
    IP address, and Service Port. This will return the nqn which can be used to connect
    over nvme on TCP protocol.
    """
    nqn = "nqn.2022-06.autobench.spdk:" + lvol_name
    cmd = [RPC_DEFAULT_PATH, 'nvmf_create_transport', '-tTCP', '-u 16384', '-m 8', '-c 8192']
    cmd1 = [RPC_DEFAULT_PATH, 'nvmf_create_subsystem', nqn, '-a', '-s', lvol_name + '001', '-d', 'autobech_spdk']
    cmd2 = [RPC_DEFAULT_PATH, 'nvmf_subsystem_add_ns', nqn, pool_name + '/' + lvol_name]
    cmd3 = [RPC_DEFAULT_PATH, 'nvmf_subsystem_add_listener', nqn, '-t', 'tcp', '-a', ip_addr, '-s', service_port]

    subprocess.run(cmd)
    subprocess.run(cmd1)
    subprocess.run(cmd2)
    subprocess.run(cmd3)

    print('NQN: ' + nqn)


if __name__ == '__main__':
    cli()
