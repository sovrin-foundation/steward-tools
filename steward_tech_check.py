#!/usr/bin/python3
import os
import sys
import platform
import subprocess
import re

#Rules definition takes care of the following item in 7.1 of:
# https://sovrin.org/wp-content/uploads/2017/06/SovrinProvisionalTrustFramework2017-03-22.pdf
# 5.a - MUST run a server operating system that receives timely patches from its vendor or
#       community. For Linux, less than 2.5 years old
#       Rule: os_allowed
#
# 7.a - Run on a mainstream hypervisor
#       Rule: machine_type_allowed
#
# 8   - Machine is dedicated to the validator, no other services 
#       Rule:ports_allowed
#
# 16  - Have 2 or more cores
#       Rule: machine_hw_required
#
# 17  - Have at least 8GB of RAM and 1-2+TB of reliable disk space
#       Rule: machine_hw_required
#             [NOTE] Hardware raid detection is only checking if a card is present not setup
#
# 18  - Must be running NTP and maintain a system clock that is demonstrably in sync within
#       two seconds.
#       Rule: procs_required
#             [NOTE] This only checks that ntpd is running, not that it is in-sync
#
# 22  - Run a firewall that disallows public ingress except on ports used by the validator
#       node software or remote administration tools.
#       Rule: firewalls_allowed
#             [NOTE] This only checks IF there are any iptables rules, not that they are
#                    blocking anything. It does NOT check if there is an external device.

rules = {
    "must": {
        "os_allowed": {
            "oses": {
                "ubuntu": [
                    "PRETTY_NAME / LTS",
                    "VERSION_ID >= 14.04"
                ],
                "debian": [
                    "VERSION_ID >= 7.0"
                ],
                "sles": [
                    "VERSION_ID >= 11.0"
                ],
                "opensuse": [
                    "VERSION_ID ranges 15-42.0,42.2-42.3"
                ],
                "opensuse-leap": [
                    "VERSION_ID ranges 15-42.0,42.2-42.3"
                ],
                "centos": [
                    "VERSION_ID >= 6.0"
                ],
                "rhel": [
                    "VERSION_ID >= 6.0"
                ]
            }
        },
        "ports_allowed": {
            "ports": {
                "tcp": [
                    {
                        'port': '= 22',
                        'prog': 'sshd'
                    },
                    {
                        'port': '= 123',
                        'prog': 'ntpd'
                    },
                    {
                        'port': '>= 9700',
                        'prog': 'python3'
                    }
                ],
                "udp": [
                    {
                        'port': '= 68',
                        'prog': 'dhclient'
                    },
                    {
                        'port': '= 123',
                        'prog': 'ntpd'
                    }
                ]
            }
        },
        "machine_type_allowed": {
            "types": {
                "vm": [ 'kvm','xen','vmware','virtualbox'],
                "container": [ 'docker','lxc' ],
                "metal": [ 'hardware' ]
            }
        },
        "machine_resources_required": {
            "resources": {
                "memory": ">= 32000000000",
                "disk": {
                    'path': "/var/indy",
                    'size': ">= 1000000000000",
                    'raid': True
                },
                'hardware': 'attested',
                'single_machine': 'attested'
            }
        },
        "procs_required": {
            'comment': '',
            'processes': [
                ['/usr/sbin/ntpd', '/lib/systemd/systemd-timesyncd']
            ]
        },
        "firewalls_allowed": {
            'comment': '',
            'firewalls': [
                'iptables',
                'attested'
            ]
        },
        "administration": {
            'rules': {
                'personel': 'attested',
                'monitoring': 'attested',
                'other_access': 'attested'
            }
        }
    }, 
    "should": {
        "machine_resources_recommended": {
            "resources": {
                "cpu_cores": ">= 2"
             }
        }, 
        "access": {
            "rules": {
                'locked_door': 'attested',
                'isolated_network': 'attested',
                'two_factor': 'attested'
            }
        },
        "availability": {
            "rules": {
                'ups': 'attested',
                'broadband': 'attested',
                'dedicated_nics': 'attested',
                'backups': 'attested'
            }
        },
        "software": {
            "rules": {
                "patching": 'attested'
            }
        } 
    }
}

class bcolors:
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'

class Node:
    def __init__(self):
        self.vm_identifiers = ['kvm','xen','vmware','innotek']
        self._os_name_map = {
                'red hat enterprise linux server': 'rhel',
                'suse linux enterprise server': 'sles'
        }
        self.os_info = self._get_os_info()
        self.os_name = self._get_os_name()
        self.os_vers = float(self.os_info['VERSION_ID'])
        self.os_type = self.os_info['TYPE']
        self.memory = self._get_memory()
        self.cpu_cores = self._get_cpu_cores()
        self.mach_type = 'Unknown'
        self.mach_tech = None
        self.is_vm = False
        self.is_container = False
        self.is_metal = False
        self._set_mach_type()

    def _get_os_info(self):
        orel_path = "/etc/os-release"
        data = {}
        data['TYPE'] = platform.system()
        if data['TYPE'] == 'Linux':
            if os.access(orel_path, os.R_OK):
                with open(orel_path,'r') as orf:
                    for l in orf.readlines():
                        lsplit = l.strip().split('=')
                        if len(lsplit) > 1:
                            data[lsplit[0]] = lsplit[1].replace('"','').strip()
            else:
                d = platform.linux_distribution()
                data['VERSION_ID'] = d[1]
                data['ID'] = d[0].lower().strip()
        else:
            print("ERROR! Unsupported OS: {}".format(data['TYPE']))
            sys.exit(1)
        return data

    def _get_os_name(self):
        name = ''
        try:
            name = self.os_info['ID']
            for n in self._os_name_map:
                if n == name:
                    name = self._os_name_map[n]
            return name.lower()
        except KeyError:
            return None

    def _get_memory(self):
        with open("/proc/meminfo","r") as meminfo:
            mi=meminfo.readline().strip().split()
            return int(mi[1]) * 1024

    def _get_cpu_cores(self):
        count = 0
        with open("/proc/cpuinfo","r") as cpuinfo:
            for l in cpuinfo.readlines():
                if l.startswith('processor'):
                    count+=1
            return count

    def _set_mach_type(self):

        try:
            output=subprocess.check_output("dmesg | grep 'Detected virtualization'", shell=True)
        except: 
            # Not a VM
            with open("/proc/1/cgroup","r") as cg:
                for l in cg.readlines():
                    lsplit = l.strip().split(':')
                    if lsplit[2] == '/':
                        self.is_metal = True
                        self.mach_type = 'metal'
                        self.mach_tech = 'hardware'
                        return
                self.is_container = True
                self.mach_type = 'container'
                self.mach_tech = lsplit[2].split('/')[1]                        
        else:
            outstr=output.decode()
            match = re.search("Detected virtualization (.*)\.", outstr)
            if match.group(1) == 'oracle':
                vm_id = 'VirtualBox'
            else:
                vm_id = match.group(1).strip()
            self.is_vm = True
            self.mach_tech = vm_id.lower()
            self.mach_type = 'vm'


    def _address_in_network(self,ip, net):
        ipaddr = int(''.join([ '%02x' % int(x) for x in ip.split('.') ]), 16)
        netstr, bits = net.split('/')
        netaddr = int(''.join([ '%02x' % int(x) for x in netstr.split('.') ]), 16)
        mask = (0xffffffff << (32 - int(bits))) & 0xffffffff
        return (ipaddr & mask) == (netaddr & mask)

    def _run_cmd(self,path,args=[],split=True,suppress_error_out=False):
        p = path
        if isinstance(path,(list,tuple,set)):
            in_path = False
            for p in path:
                if os.access(p, os.X_OK):
                    in_path = True
                    break
            if not in_path:
                if not suppress_error_out:
                    print("Error! Can't find executable here: {}".format(path))
                    return (-1,"Error! Can't find executable here: {}".format(path))
        else:
            if not os.access(p,os.X_OK):
                if not suppress_error_out:
                    print("Error! Can't find executable here: {}".format(p))
                return (-1,"Error! Can't find executable here: {}".format(p))
        pr = subprocess.Popen([p] + args,shell=False,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
        pr_out,stderr = pr.communicate()
        if pr.returncode > 0:
            if not suppress_error_out:
                print("Error! running {} {}:".format(p,' '.join(args)))
                print(stderr)
            out = stderr.decode('ascii','ignore')
        else:
            out = pr_out.decode('ascii','ignore')
        if split:
            out = out.splitlines()
        return (pr.returncode,out)

    def iptables_running(self):
        iptables_save_path = ['/sbin/iptables-save','/usr/sbin/iptables-save']
        if os.getuid() != 0:
            print("WARNING: You are not root, won't be able to check iptables")
            return False
        ipts_p = self._run_cmd(iptables_save_path)
        if ipts_p[0] == 0:
            for l in ipts_p[1]:
                if l[0] in [':','#']:
                    continue
                return True
        return False

    def mount_for_path(self,path):
        cpath = os.path.realpath(path)
        while not os.path.ismount(cpath):
            cpath = os.path.dirname(cpath)
        return cpath

    def path_exists(self,path):
        return os.path.exists(path)

    def get_dev_for_mount(self,path):
        dev = None
        with open("/proc/mounts","r") as mounts:
            mount_list=mounts.readlines()
            for m in mount_list:
                device,mount_point,fs,opts,d,co = m.strip().split()
                if device[0] == '/' and path == mount_point:
                    dev = device
                    break
        return dev

    def get_dev_for_path(self,path):
        m = self.mount_for_path(path)
        dev = self.get_dev_for_mount(m)
        if not dev:
            print("Error, couldn't find device for path: {}".format(path))
        return dev

    def get_storage_size_for_path(self,path):
        mount = self.mount_for_path(path)
        return self.get_storage_size(mount)

    def get_storage_size(self,mount):
        df_paths = ['/usr/bin/df','/bin/df']
        size = -1
        s = self._run_cmd(df_paths,['-k',mount])
        if s[0] == 0:
            size = int(s[1][1].strip().split()[1]) * 1024
        return size

    def get_storage_details(self,dev):
        mdstat = '/proc/mdstat'
        lvdisplay_path = '/sbin/lvdisplay'
        pvdisplay_path = '/sbin/pvdisplay'
        dmraid_path = '/sbin/dmraid'
        lspci_path = [ '/sbin/lspci', '/usr/bin/lspci' ]
        data = {'type': 'standard'}
        while True:
            if os.access(mdstat,os.R_OK):
                with open(mdstat,"r") as mdf:
                    found = False
                    for l in mdf.readlines():
                        line = l.strip()
                        if not ':' in line:
                            continue
                        lsplit = line.split(':')
                        det = lsplit[1].split()
                        d = lsplit[0].strip()
                        if dev == '/dev/{}'.format(d):
                            data['raid'] = {}
                            data['raid']['method'] = 'md'
                            data['raid']['level'] = det[1]
                            data['raid']['devices'] = det[2:]
                            data['type'] = 'raid'
                            found = True
                            break
                    if found:
                        break
            lvd_p = self._run_cmd(lvdisplay_path,['-c',dev],suppress_error_out=True)
            if lvd_p[0] == 0:
                data['lvm'] = {}
                data['type'] = 'lvm'
                for l in lvd_p[1]:
                    lsplit = l.strip().split(':')
                    data['lvm']['vg'] = lsplit[1]
                    pvd_p = self._run_cmd(pvdisplay_path,['-c'],suppress_error_out=True)
                    if pvd_p[0] == 0:
                        data['lvm']['pv'] = []
                        for pl in pvd_p[1]:
                            plsplit = pl.strip().split(':')
                            if plsplit[1] == data['lvm']['vg']:
                                data['lvm']['pv'].append(plsplit[0])
                        for p in data['lvm']['pv']:
                            td = self.get_storage_details(p)
                            if 'raid' in td:
                                if not 'raid' in data['lvm']:
                                    data['lvm']['raid'] ={}
                                    data['lvm']['raid']['raided_pvs'] = []
                                    data['lvm']['raid']['methods'] = []
                                    data['lvm']['raid']['devices'] = []
                                    data['lvm']['raid']['levels'] = []
                                data['lvm']['raid']['raided_pvs'].append(p)
                                data['lvm']['raid']['devices'] += td['raid']['devices']
                                data['lvm']['raid']['methods'].append(td['raid']['method'])
                                data['lvm']['raid']['levels'].append(td['raid']['level'])
                                if 'card' in td['raid']:
                                    data['lvm']['raid']['card'] = td['raid']['card']
                break
            else:
                if 'WARNING: Running as a non-root user' in ''.join(lvd_p[1]):
                    print("WARNING: Unable to check if storage is on LVM, run as root to check")
            dmr_p = self._run_cmd(dmraid_path,['-r'],suppress_error_out=True)
            if dmr_p[0] == 0:
                data['raid'] = {}
                data['raid']['method'] = 'fakeraid'
                data['raid']['level'] = ''
                data['raid']['devices'] =[]
                data['type'] = 'raid'
                for l in dmr_p[1]:
                    lsplit = l.strip().split(':')
                    det = lsplit[1].strip().split(',')
                    if '/dev/mapper/{}'.format(det[1].strip().strip('"')) == dev:
                        data['raid']['devices'].append(lsplit[0])
                        data['raid']['level'] = det['2']
                break
            else:
                if dmr_p[1]:
                    if "Can't find executable" not in dmr_p[1]:
                        print("ERROR running 'dmraid' to check for fakeraid:")
                        print(dmr_p[1])
            lspci_p = self._run_cmd(lspci_path,['-v'],suppress_error_out=True)
            if lspci_p[0]:
                for l in lspci_p[1]:
                    if 'raid' in l.lower():
                        data['raid'] = {}
                        data['raid']['method'] = 'guess_hwraid'
                        data['raid']['level'] = 'Unknown'
                        data['raid']['devices'] = []
                        data['raid']['card'] = l.strip()
                        data['type'] = 'raid'
                        break
                break
            break
        return data

    def running_procs(self):
        ps_paths = ['/usr/bin/ps','/bin/ps']
        procs = []
        ps_p = self._run_cmd(ps_paths,['-eo','pid,cmd'])
        if ps_p[0] == 0:
            for line in ps_p[1][1:]:
                lsplit = line.strip().split()
                pid = lsplit[0]
                cmd = ' '.join(lsplit[1:])
                procs.append({'pid': pid, 'cmd': cmd})
        return procs

    def rpc_ports(self):
        data = {}
        rpcinfo_path = '/usr/sbin/rpcinfo'
        rpc_p = self._run_cmd(rpcinfo_path,['-p'],suppress_error_out=True)
        if rpc_p[0] == 0:
                for line in rpc_p[1][1:]:
                    lsplit = line.strip().split()
                    proto,port,service = lsplit[2:5]
                    try:
                        data[proto][port] = service
                    except KeyError:
                        data[proto] = {}
                        data[proto][port] = service
        else:
            if not 'No such file or directory' in ''.join(rpc_p[1]):
                print("Error running 'rpcinfo -p' to check additional rpc ports")
                print(rpc_p[1])
        return data

    def listening_ports(self):
        data = {}
        ss = False
        ss_to_ns_col = [0,2,3,4,5,1,6]
        if self.os_type == "Linux":
            netstat_path = '/bin/netstat'
            ss_path = ['/bin/ss', '/usr/bin/ss']
            protos = ['tcp','tcp6','udp', 'udp6']
            ns_p = (-1,'')
            if self.path_exists(netstat_path):
                ns_p = self._run_cmd(netstat_path,['-ntulp'])
            if ns_p[0] == -1:
                ns_p = self._run_cmd(ss_path,['-ntulp'])
                ss = True
            if ns_p[0] == -1:
                print("Error, can't find netstat OR ss")
                return False
            if ns_p[0] == 0:
                rpc_loaded = False
                rpc_data = {}
                for line in ns_p[1]:
                    lsplit = line.strip().split()
                    if len(lsplit) > 1:
                        #Format ss's output to match netstat's
                        if ss:
                            #Make sure we have 7 columns, missing one means no pid/proc name
                            if len(lsplit) < 7:
                                lsplit.append('-')
                            else:
                                #Skip header row
                                if lsplit[6] == 'Peer':
                                    continue
                                #Format pid/proc like netstat's
                                ss_p = lsplit[6].replace('users:((','').replace('))','').replace('"','').split(',')
                                lsplit[6] = '{}/{}'.format(ss_p[1].split('=')[1],ss_p[0])
                            #Reorder the columns
                            lsplit = [ lsplit[i] for i in ss_to_ns_col ]
                            #Replace * with 0.0.0.0, and strip out square brackets
                            lsplit[3] = lsplit[3].replace('*','0.0.0.0').replace('[','').replace(']','')
                            #Set proto correctly if ipv6 address
                            if lsplit[3].count(':') > 1:
                                lsplit[0]+='6'
                        proto = lsplit[0]
                        if proto in protos:
                            v6 = False
                            if proto.endswith('6'):
                                v6 = True
                                proto = proto.rstrip('6')
                            local = False
                            lface = lsplit[3].split(':')
                            iface = ':'.join(lface[:-1])
                            port = lface[-1]
                            if lsplit[5] in [ 'LISTEN', 'UNCONN']:
                                prog_pid = ' '.join(lsplit[6:]).split('/')
                            else:
                                prog_pid = ' '.join(lsplit[5:]).split('/')
                            if prog_pid[0] == '-':
                                prog = '-'
                                pid = '-'
                                if not rpc_loaded:
                                    rpc_data = self.rpc_ports()
                                    rpc_loaded = True
                                try:
                                    prog = 'rpc:{}'.format(rpc_data[proto][port])
                                    pid = '0'
                                except KeyError:
                                    pass
                            else:
                                pid,prog = prog_pid
                            if iface == '::1':
                                local = True
                            elif iface == '::':
                                local = False
                            elif ':' in iface:
                                if iface.startswith('fe80:'):
                                    local = True
                                else:
                                    local = False
                            else:
                                local = self._address_in_network(iface,'127.0.0.1/8')
                            d = {
                                    'iface': iface,
                                    'local': local,
                                    'port': port,
                                    'prog': prog,
                                    'pid': pid,
                                    'v6': v6,
                            }
                            try:
                                data[proto].append(d)
                            except KeyError:
                                data[proto] = []
                                data[proto].append(d)
                return data


class RuleValidator:
    def __init__(self,rules,node):
        self.must_rules_map = {
            'firewalls_allowed': self.eval_fw_allowed,
            'machine_resources_required': self.eval_mach_resources_required,
            'machine_type_allowed': self.eval_mach_type_allowed,
            'os_allowed': self.eval_os_allowed,
            'ports_allowed': self.eval_ports_allowed,
            'procs_required': self.eval_procs_req,
            'administration': self.eval_administration

        }
        self.should_rules_map = {
            'machine_resources_recommended': self.eval_mach_resources_recommended,
            'access': self.eval_access,
            'availability': self.eval_availability,
            'software': self.eval_software
        }
        self.must_results = {}
        self.should_results = {}
        for k in rules["must"]:
            if k not in self.must_rules_map:
                raise ValueError("Unknown rule: {}".format(k))
        for k in rules["should"]:
            if k not in self.should_rules_map:
                raise ValueError("Unknown rule: {}".format(k))
        self.must_rules = rules["must"]
        self.should_rules = rules["should"]
        self.node = node

    def _compare(self,lefthand,op,righthand):
        if op in ['>','>=','<','<=','=']:
            lh = float(lefthand)
            rh = float(righthand)
        if op == '>':
            return lh > rh
        elif op == '>=':
            return lh >= rh
        elif op == '<':
            return lh < rh
        elif op == '<=':
            return lh <= rh
        elif op == '=':
            return lh == rh
        elif op in [ '/', 'in' ]:
            if isinstance(righthand,(list,tuple,set)):
                rh = righthand
            elif ',' in righthand:
                rh = righthand.split(',')
            else:
                rh = str(righthand)
            return rh in str(lefthand)
        elif op == 'ranges':
            ranges = righthand.split(',')
            nir = False
            lh = float(lefthand)
            for r in ranges:
                rl,rr = r.split('-')
                if lh >= float(rl) and lh <= float(rr):
                    return True
            return False
        elif op == 'in':
             
            return lefthand in righthand
        else:
            raise ValueError("Unknown operator: {}".format(op))

    def _comp_exec(self,cur,comp_str,rule_str=''):
        comp_args = comp_str.split()
        if len(comp_args) < 2:
            raise ValueError("Invalid Rule: {}: {}".format(rule_str,comp_str))
        return self._compare(cur,comp_args[0],comp_args[1])

    def _attest(self,prompt):
        while True:
            # DEBUG
            #response = 'y'
            response = input(prompt + " (y/n): ")
            if response.lower() not in ('y', 'n'):
                print("Please choose y (yes) or n (no)")
            else:
                break 
        if response.lower() in ('y'):
            return True
        else:
            return False

    def validate(self):
        rk = list(self.must_rules.keys())
        rk.sort()
        for r in rk:
            self.must_results[r] = self.must_rules_map[r](self.must_rules[r])
        rk = list(self.should_rules.keys())
        rk.sort()
        for r in rk:
            self.should_results[r] = self.should_rules_map[r](self.should_rules[r])

    def print_report(self):
        print(bcolors.BOLD + '== Results for "A Steward MUST" ==' + bcolors.ENDC)
        rk = list(self.must_results.keys())
        rk.sort()
        indent_level='    '
        rule_data = ['result', 'details', 'action_needed']
        for r in rk:
            print("Rule: {}:".format(r))
            for rdk in rule_data:
                rd = self.must_results[r][rdk]
                if isinstance(rd,(list,tuple,set)):
                    print("{}{}:".format(indent_level,rdk))
                    for i in rd:
                        print('{il}{il}{d}'.format(il=indent_level,d=i))
                else:
                    print("{}{}: {}".format(indent_level,rdk,rd))
        print(bcolors.BOLD + '== Results for "A Steward SHOULD" ==' + bcolors.ENDC)
        rk = list(self.should_results.keys())
        rk.sort()
        indent_level='    '
        rule_data = ['result', 'details', 'action_needed']
        for r in rk:
            print("Rule: {}:".format(r))
            for rdk in rule_data:
                rd = self.should_results[r][rdk]
                if isinstance(rd,(list,tuple,set)):
                    print("{}{}:".format(indent_level,rdk))
                    for i in rd:
                        print('{il}{il}{d}'.format(il=indent_level,d=i))
                else:
                    print("{}{}: {}".format(indent_level,rdk,rd))

    def eval_administration(self,criteria):
        res =  {
            'result': 'UNKNOWN',
            'action_needed': [],
            'details': [],
            'comment': 'None'
        }
        if 'personel' in criteria["rules"]:
            if self._attest("At least one qualifed adminstrator is assigned to administer the node, and at least one other person has adequate access and training to administer the box in an emergency."):
                res['result'] = bcolors.OKGREEN + "PASSED" + bcolors.ENDC
                res['details'].append("Appropriate administrative personnel is assigned")
            else:
                res['result'] = bcolors.FAIL + "FAILED" + bcolors.ENDC
                res['action_needed'].append("Assign qualified administrators")
                res['details'].append("Inadequate administrative personnel assigned")
        if 'other_access' in criteria['rules']:
            if self._attest("Persons who are not designated administrators of the validator node have access to the system."):
                res['result'] = bcolors.FAIL + "FAILED" + bcolors.ENDC
                res['action_needed'].append("Modify access rules to only allow access by designated administrators")
                res['details'].append("Access control rules are insufficiently restrictive")
            else:
                res['details'].append("Access control rules are appropriate")
        if 'monitoring' in criteria['rules']:
            if self._attest("Monitoring is in place that provides notification if the OS crashes, if the sovrin daemon abends, or if abnormal spikes in resource usage occur."):
                res['details'].append("Node and service monitoring is in place")
            else:
                res['result'] = bcolors.FAIL + "FAILED" + bcolors.ENDC
                res['action_needed'].append("Implement monitoring of the node and the Sovrin service")
                res['details'].append("Monitoring is not implemented on the node or Sovrin service")
        return res

    def eval_access(self,criteria):
        res =  {
            'result': 'UNKNOWN',
            'action_needed': [],
            'details': [],
            'comment': 'None'
        }
        if 'locked_door' in criteria["rules"]:
            if self._attest("Hardware is in a locked datacenter with at least one layer of keycard access."):
                res['result'] = bcolors.OKGREEN + "PASSED" + bcolors.ENDC
                res['details'].append("Physical security provided")
            else:
                res['result'] = bcolors.FAIL + "FAILED" + bcolors.ENDC
                res['action_needed'].append("Move node to a secure datacenter")
                res['details'].append("Inadequate physical security")
        if 'isolated_network' in criteria['rules']:
            if self._attest("The node is logically isolated from steward internal systems and networks."):
                res['details'].append("Node is isolated from Steward internal networks")
            else:
                res['result'] = bcolors.FAIL + "FAILED" + bcolors.ENDC
                res['action_needed'].append("Move node to an exterior-facing network")
                res['details'].append("Node has logical access to internal resources that it should not have access to")
        if 'two_factor' in criteria['rules']:
            if self._attest("Two-factor authentication is required for all access to node."):
                res['details'].append("Secure authenticaton policies applied")
            else:
                res['result'] = bcolors.FAIL + "FAILED" + bcolors.ENDC
                res['action_needed'].append("Implement two-factor authentication policy")
                res['details'].append("Authentication incorrectly does not require two factors.")
        return res

    def eval_availability(self,criteria):
        res =  {
            'result': 'UNKNOWN',
            'action_needed': [],
            'details': [],
            'comment': 'None'
        }
        if 'ups' in criteria["rules"]:
            if self._attest("The system will remain functional through blackouts or brownouts up to 60 minutes duration."):
                res['result'] = bcolors.OKGREEN + "PASSED" + bcolors.ENDC
                res['details'].append("System power is resilient")
            else:
                res['result'] = bcolors.FAIL + "FAILED" + bcolors.ENDC
                res['action_needed'].append("Provide robust power for the node")
                res['details'].append("System is not able to remain functional through modest power supply interruptions")
        if 'broadband' in criteria['rules']:
            if self._attest("Internet connectivity is via high-reliabity, high-speed connection(s)."):
                res['details'].append("Appropriate network connectivity is provided")
            else:
                res['result'] = bcolors.FAIL + "FAILED" + bcolors.ENDC
                res['action_needed'].append("Provide enterprise-quality connection to the internet")
                res['details'].append("Inadequate connection to the internet is provided")
        if 'dedicated_nics' in criteria['rules']:
            if self._attest("The node has two NICs, one each for validator traffic and for client traffic. "):
                res['details'].append("Requested NICs provided")
            else:
                res['result'] = bcolors.FAIL + "FAILED" + bcolors.ENDC
                res['action_needed'].append("Provide independent NICs for validator vs. client traffic")
                res['details'].append("A single NIC, not two dedicated NICs, is provided.")
        if 'backups' in criteria['rules']:
            if self._attest("A snapshot or backup of the system is maintained, with the ability to restore in one hour."):
                res['details'].append("Snapshot or backup of the system is maintained")
            else:
                res['result'] = bcolors.FAIL + "FAILED" + bcolors.ENDC
                res['action_needed'].append("Implement snapshots or system backups")
                res['details'].append("No system backup is maintained")
        return res

    def eval_software(self,criteria):
        res =  {
            'result': 'UNKNOWN',
            'action_needed': [],
            'details': [],
            'comment': 'None'
        }
        if 'patching' in criteria["rules"]:
            if self._attest("Policies and practices provide for application of new security patches within 1 week of release."):
                res['result'] = bcolors.OKGREEN + "PASSED" + bcolors.ENDC
                res['details'].append("Patching occurs in timely fashion")
            else:
                res['result'] = bcolors.FAIL + "FAILED" + bcolors.ENDC
                res['action_needed'].append("Develop policies and practices for rapid deployment of patches")
                res['details'].append("Software patches are not applied within a week")
        return res

    def eval_fw_allowed(self,criteria):
        res =  {
            'result': 'UNKNOWN',
            'action_needed': 'None',
            'details': '',
            'comment': 'None'
        }
        # default to failed
        res['result'] = bcolors.FAIL + "FAILED" + bcolors.ENDC
        res['action_needed'] = "Protect your validator with a firewall"
        res['details'] = "No iptables nor attested firewall"
        if 'iptables' in criteria['firewalls']:
            if self.node.iptables_running():
                res['result'] = bcolors.OKGREEN + "PASSED" + bcolors.ENDC
                res['action_needed'] = "Verify that iptables rules are blocking appropriately"
                res['details'] = "Local firewall (iptables) detected"
        if 'attested' in criteria['firewalls']:
            if self._attest("Do you run an external firewall that protects the validator?"):
                res['result'] = bcolors.OKGREEN + "PASSED" + bcolors.ENDC
                res['action_needed'] = "Verify that your firewall rules are blocking appropriately"
                if "No iptables" in res['details']:
                    res['details'] = "Administrator indicates that an external firewall is in use"
                else:
                    res['details'] = res['details'] + ".  Administrator also indicates that an external firewall is in use"
        try:
            res['comment'] = criteria['comment']
        except KeyError:
            pass
        return res

    def eval_mach_resources_required(self,criteria):
        res =  {
            'result': 'UNKNOWN',
            'action_needed': [],
            'details': [],
            'comment': 'None'
        }
        er = True
        for r in criteria['resources']:
            if r == "memory":
                memory = self.node.memory
                if not self._comp_exec(
                        self.node.memory,
                        criteria['resources'][r],
                        'mach_resources_required.memory'
                    ):
                    if er:
                        er = False
                    res['result'] = bcolors.FAIL + "FAILED" + bcolors.ENDC
                    res['details'].append("{}: Not enough memory, only found: {}".format(r,memory))
                    res['action_needed'].append("Change memory to be: {}".format(criteria['resources'][r]))
                else:
                    res['details'].append("{}: Found enough memory: {}".format(r,memory))
            elif r == "disk":
                try:
                    d_mount = self.node.mount_for_path(
                        criteria['resources'][r]['path']
                    )
                    d_dev = self.node.get_dev_for_mount(d_mount)
                    d_size = self.node.get_storage_size(d_mount)
                    path_exists = self.node.path_exists(criteria['resources'][r]['path'])
                    if path_exists:
                        res['details'].append(
                            "{}: Found path: {} exists".format(
                                r,
                                criteria['resources'][r]['path']
                            )
                        )
                    else:
                        res['result'] = bcolors.FAIL + "FAILED" + bcolors.ENDC
                        res['details'].append(
                            "{}: Path: {} NOT found".format(
                                r,
                                criteria['resources'][r]['path']
                            )
                        )
                        res['action_needed'].append(
                            "{}: Create path: {}".format(
                                r,
                                criteria['resources'][r]['path']
                            )
                        )
                    if not self._comp_exec(
                        d_size,
                        criteria['resources'][r]['size'],
                        'mach_resources_required.disk.size'
                    ):
                        if er:
                            er = False
                        res['result'] = bcolors.FAIL + "FAILED" + bcolors.ENDC
                        res['details'].append(
                            "{}: Not enough storage space for path: {} mounted at: {} from device: {}. Only found: {} bytes".format(
                                r,
                                criteria['resources'][r]['path'],
                                d_mount,
                                d_dev,
                                d_size
                            )
                        )
                        res['action_needed'].append("Change storage space for path: {} mounted at: {} from device: {} to be {}".format(
                                criteria['resources'][r]['path'],
                                d_mount,
                                d_dev,
                                criteria['resources'][r]['size']
                            )
                        )
                    else:
                        res['result'] = bcolors.FAIL + "FAILED" + bcolors.ENDC
                        res['details'].append("{}: Found enough storage space for path: {}, {} bytes".format(
                                r,
                                criteria['resources'][r]['path'],
                                d_size
                            )
                        )
                except KeyError:
                    raise ValueError(
                        "Invalid Rule: {}: {}".format(
                            'machine_resources_required.resources.disk.path',
                            criteria['resources'][r]['path']
                            )
                        )
                if 'raid' in criteria['resources'][r]:
                    d_dev = self.node.get_dev_for_path(
                        criteria['resources'][r]['path']
                    )
                    st_details = self.node.get_storage_details(d_dev)
                    raided = 'raid' in st_details
                    if criteria['resources'][r]['raid'] != raided:
                        if self._attest("This system utilizes an external RAID system for storage."):
                            res['details'].append("{}: An external RAID is in use".format(r))
                        else:
                            if er:
                                er = False
                            res['result'] = bcolors.FAIL + "FAILED" + bcolors.ENDC
                            res['details'].append(
                                "{}: Storage space for path: {}, doesn't meet raid requirements, raided is: {}".format(
                                    r,
                                    criteria['resources'][r]['path'],
                                    raided
                                )
                            )
                            res['action_needed'].append("Modify the storage for path: {} to be raided: {}".format(
                                    criteria['resources'][r]['path'],
                                    criteria['resources'][r]['raid']
                                )
                            )
                    else:
                        res['details'].append("{}: A RAID is used for storage".format(r))
            elif r == 'hardware':
                if self._attest("This node is on server-class hardware that is less than 4 years old?"):
                    res['details'].append("{}: Node is on current, server-class hardware".format(r))
                else:
                    er = False
                    res['result'] = bcolors.FAIL + "FAILED" + bcolors.ENDC
                    res['details'].append("{}: Node is not on current, server-class hardware".format(r))
                    res['action_needed'].append("Upgrade to current, server-class hardware")
            elif r == 'single_machine':
                if self._attest("This node is a single machine, not a cluster"):
                    res['details'].append("{}: Node is a single machine".format(r))
                else:
                    er = False
                    res['result'] = bcolors.FAIL + "FAILED" + bcolors.ENDC
                    res['details'].append("{}: Node ia clustered.  Should be a single machine".format(r))
                    res['action_needed'].append("Stand up a single-server replacement")
            else:
                raise ValueError(
                    "Invalid Rule: mach_resources_required.{}: {}".format(
                        r,
                        criteria['resources'][r]
                    )
                )
        if er:
            res['result'] = bcolors.OKGREEN + "PASSED" + bcolors.ENDC
        return res

    def eval_mach_resources_recommended(self,criteria):
        res =  {
            'result': 'UNKNOWN',
            'action_needed': [],
            'details': [],
            'comment': 'None'
        }
        er = True
        for r in criteria['resources']:
            if r == "cpu_cores":
                cpu_cores = self.node.cpu_cores
                if not self._comp_exec(
                        cpu_cores,
                        criteria['resources'][r],
                        'mach_resources_required.cpu_cores'
                    ):
                    if er:
                        er = False
                    res['result'] = bcolors.FAIL + "FAILED" + bcolors.ENDC
                    res['details'].append("{}: Not enough cores, only found: {}".format(r,cpu_cores))
                    res['action_needed'].append("Change CPU cores to be: {}".format(criteria['resources'][r]))
                else:
                    res['details'].append("{}: Found enough cores: {}".format(r,cpu_cores))
            else:
                raise ValueError(
                    "Invalid Rule: mach_resources_required.{}: {}".format(
                        r,
                        criteria['resources'][r]
                    )
                )
        if er:
            res['result'] = bcolors.OKGREEN + "PASSED" + bcolors.ENDC
        return res

    def eval_mach_type_allowed(self,criteria):
        res =  {
            'result': 'UNKNOWN',
            'action_needed': 'None',
            'details': '',
            'comment': 'None'
        }
        mach_type = self.node.mach_type
        mach_tech = self.node.mach_tech
        if mach_type in criteria['types']:
            if mach_tech in criteria['types'][mach_type]:
                res['result'] = bcolors.OKGREEN + "PASSED" + bcolors.ENDC
                res['details'] = "Found a valid machine_type: {} on a valid technology: {}".format(mach_type,mach_tech)
            else:
                res['result'] = bcolors.FAIL + "FAILED" + bcolors.ENDC
                res['action_needed'] = "Found valid machine_type: {} running on Unsupported technology: {}".format(mach_type,mach_tech)
                res['details'] = "Found valid machine_type: {} on unsupported technology: {}".format(mach_type,mach_tech)
        else:
            res['result'] = bcolors.FAIL + "FAILED" + bcolors.ENDC
            res['action_needed'] = "Change to a supported machine type of: {}".format(','.join(criteria['types']))
            res['details'] = "Found Unsupported machine_type: {} on technology: {}".format(mach_type,mach_tech)
        return res

    def eval_os_allowed(self,criteria):
        res =  {
            'result': 'UNKNOWN',
            'action_needed': [],
            'details': [],
            'comment': 'None'
        }
        cur_os = self.node.os_name
        cur_os_ver = self.node.os_vers
        failed = False
        if cur_os in criteria['oses']:
            res['details'].append("Found valid OS: {}".format(cur_os))
            for sc in criteria['oses'][cur_os]:
                sc_split = sc.split()
                os_d=sc.split()[0]
                try:
                    v = self.node.os_info[os_d]
                    if not self._compare(v,sc_split[1],sc_split[2]):
                        failed = True
                        res['result'] = bcolors.FAIL + 'FAILED' + bcolors.ENDC
                        res['action_needed'].append('Update OS so that {} matches: {}'.format(os_d,sc))
                        res['details'].append("OS doesn\'t match rule: {}: {} is {}".format(sc,os_d,v))
                    else:
                        res['details'].append("OS meets match rule: {}: {} is {}".format(sc,os_d,v))
                except KeyError:
                    failed = -1
                    res['details'].append("Can't check os_info about: {}, as it is missing!".format(os_d))
                    res['action_needed'] = "OS release information: {} is missing. Either provide a valid os release information value, or make sure /etc/os-release contains it."
                except IndexError:
                    raise ValueError("Invalid rule os_allowed.oses.{}: {} must have 3 values.".format(cur_os,os_d))
        else:
            failed = True
            res['result'] = bcolors.FAIL + 'FAILED' + bcolors.ENDC
            res['detail'] = 'Currently installed os is not allowed: {}'.format(cur_os)
            res['action_needed'] = "Install a permitted OS: {}".format(','.join(criteria['oses']))
        if not failed:
            res['result'] = bcolors.OKGREEN + "PASSED" + bcolors.ENDC
        return res

    def eval_ports_allowed(self,criteria):
        res =  {
            'result': 'UNKNOWN',
            'action_needed': [],
            'details': [],
            'comment': 'None'
        }
        prohibited_ports = [];
        lports = self.node.listening_ports()
        failed = False
        res['details'].append("Allowed ports found:")
        for proto in criteria['ports']:
            if proto not in lports:
                continue
            for lpp in lports[proto]:
                if not lpp['local']:
                    allowed = False
                    for ap in criteria['ports'][proto]:
                        if self._comp_exec(lpp['port'],ap['port'],'ports_allowed.{}:{}'.format(proto,ap)):
                            allowed = True
                            res['details'].append("   Non-local listening proto: {proto}, port: {iface}:{port}, prog: {prog}, pid: {pid}".format(proto=proto,**lpp))
                            break
                    if not allowed:
                        failed = True
                        res['result'] = bcolors.FAIL + 'FAILED' + bcolors.ENDC
                        prohibited_ports.append("   Non-local listening proto: {proto}, port: {iface}:{port}, prog: {prog}, pid: {pid}".format(proto=proto,**lpp))
                        res['action_needed'].append("Stop program/pid: {prog}/{pid} from listening on non-local proto: {proto}, port: {iface}:{port}".format(proto=proto,**lpp))
                else:
                    res['details'].append("   Local listening proto: {proto}, port: {iface}:{port}, prog: {prog}, pid: {pid}".format(proto=proto,**lpp))
        res['details'].append("Prohibited ports found:")
        for prohibited_port in prohibited_ports:
            res['details'].append(prohibited_port)
        if not failed:
            res['result'] = bcolors.OKGREEN + "PASSED" + bcolors.ENDC
        return res

    def eval_procs_req(self,criteria):
        res =  {
            'result': 'UNKNOWN',
            'action_needed': [],
            'details': [],
            'comment': 'None'
        }
        cur_procs = self.node.running_procs()
        failed = False
        for processes in criteria['processes']:
            fp = False
            for cp in cur_procs:
                if isinstance(processes, str):
                    processes = [processes]
                if cp['cmd'].split()[0] in processes:
                    fp = True
                    res['details'].append('Found required proc: {} at pid: {}'.format(cp['cmd'],cp['pid']))
                    break
            if not fp:
                failed = True
                res['result'] = bcolors.FAIL + 'FAILED' + bcolors.ENDC
                res['action_needed'].append("Start required process: {}".format(', '.join(processes)))
                res['details'].append("Can't find required process: {}".format(', '.join(processes)))
        if not failed:
            res['result'] = bcolors.OKGREEN + "PASSED" + bcolors.ENDC
        return res

if __name__ == '__main__':
    node = Node()
    rule_validator = RuleValidator(rules,node)
    rule_validator.validate()
    rule_validator.print_report()
