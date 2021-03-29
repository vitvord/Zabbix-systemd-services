#!/usr/bin/env python3

"""
Script return Zabbix format JSON with systemd services list - if no args
    {"data": [{"{#NAME}": "ethers.service", "{#STATUS}": "disabled"},....

and individual services status.
    {"data": [{"Status": 0, "Startup": 0, "Condition": 0}]}

Script ignore services without enabled/disabled state and not a .service name

You can filter services list using the files (one service per line):
    DISCOVERY_WHITELIST - select ONLY services in this file
    DISCOVERY_BLACKLIST - exclude services from file
    ! Only one file can be loaded. The whitelist file is loaded first.
"""

import json
import re
import subprocess
import sys
import os.path

DISCOVERY_WHITELIST = '/opt/zabbix/service_discovery_whitelist'
DISCOVERY_BLACKLIST = '/opt/zabbix/service_discovery_blacklist'

STARTUP_MAP = {
    'disabled': 0,
    'enabled': 1,
    'static': 2,
    'indirect': 3,
}
STATUS_MAP = {
    'dead': 0,
    'running': 1,
    'exited': 2,
    'start': 3,
    'Result: exit - code': 4
}
CONDITION_MAP = {
    'no': 0,
    'start': 1,
    None: 0,
}


def get_service_status(service_name: str):
    status = {
        'Status': 0,
        'Startup': 0,
        'Condition': 0,
    }
    output = ''

    try:
        output = subprocess.check_output(['/usr/bin/systemctl', 'status', service_name],
                                         errors='ignore', encoding='utf-8',
                                         universal_newlines=True, stderr=subprocess.DEVNULL)
    except subprocess.CalledProcessError as e:
        # systemctl exit code > 0 if service is in running state. Skip this exceptions type for further actions.
        output = e.output
    except Exception as e:
        print(f"Can't get status for service {service_name}. Error: {repr(e)}")
        sys.exit()
    if output:
        status_output = re.search(r'[ |\t]+Active: \w+ \((\w+)\)', output)
        startup_output = re.search(r'Loaded: \w+ \(.*; (\w+);.*\)', output)
        condition_output = re.search(r'Condition: (no|start)', output)

        status_data = status_output[1] if status_output else None
        startup_data = startup_output[1] if startup_output else None
        condition_data = condition_output[1] if condition_output else None
        status['Status'] = STATUS_MAP.get(status_data, -1)
        status['Startup'] = STARTUP_MAP.get(startup_data, -1)
        status['Condition'] = CONDITION_MAP.get(condition_data, -1)

    print(json.dumps(status))


def get_all_services():
    try:
        output = subprocess.check_output(['/usr/bin/systemctl', 'list-unit-files'], universal_newlines=True)
    except:
        print(f"Can't get the services status")
        sys.exit(1)

    if output:
        output = output.split('\n')
    else:
        print("Can't get services list")
        sys.exit(1)

    # Filter services. Work only one filter
    if os.path.isfile(DISCOVERY_WHITELIST):
        result = parse_services_includeonly(output)
    elif os.path.isfile(DISCOVERY_BLACKLIST):
        result = parse_services_exclude(output)
    else:
        result = parse_services(output)
    print(result)


def parse_services_includeonly(strings: list):
    with open(DISCOVERY_WHITELIST, 'r') as f:
        # read file and remove newline
        include_lines = [x.rstrip() for x in f.readlines()]
    if include_lines:
        filtered_strings = [s for s in strings if any(x in s for x in include_lines)]
    else:
        filtered_strings = strings
    return parse_services(filtered_strings)


def parse_services_exclude(strings: list):
    with open(DISCOVERY_BLACKLIST, 'r') as f:
        # read file and remove newline
        exclude_lines = [x.rstrip() for x in f.readlines()]
    if exclude_lines:
        filtered_strings = [s for s in strings if not any(x in s for x in exclude_lines)]
    else:
        filtered_strings = strings
    return parse_services(filtered_strings)


def parse_services(strings: list) -> str:
    services = []
    for string in strings:
        if '.service' in string and ('enabled' in string or 'disabled' in string):
            tmp = re.search(r'(\w+\.\w+)\s+(\w+)', string)
            if not tmp:
                continue
            services.append({
                '{#NAME}': tmp[1],
                '{#STATUS}': tmp[2],
            })
    return json.dumps({'data': services})


def main(service: str = None):
    if service:
        get_service_status(service)
    else:
        get_all_services()


def allowed_service_name(srv_name: str) -> bool:
    if re.search(r'[\[\] \| &\(\);]', srv_name):
        return False
    return True


if __name__ == '__main__':
    service_name = ''
    if len(sys.argv) >= 2 or sys.argv == '-h' or sys.argv == '--help':
        print("""
        Script return Zabbix format JSON with systemd services list - if no args
        {"data": [{"{#NAME}": "ethers.service", "{#STATUS}": "disabled"},....
        and individual services status.
        {"data": [{"Status": 0, "Startup": 0, "Condition": 0}]}

        Script ignore services without enabled/disabled state and not a .service name

        You can filter services list using the files (one service per line):
        DISCOVERY_WHITELIST - select ONLY services in this file
        DISCOVERY_BLACKLIST - exclude services from file
        ! Only one file can be loaded. The whitelist file is loaded first.
        
        Usage: services-status.py [SERVICE]
            without parameters return systemd services -  status JSON list
            with SERVICE - return a service status JSON string
                "Status":
                        'dead': 0,
                        'running': 1,
                        'exited': 2,
                        'start': 3,
                        'Result: exit - code': 4
                "Startup":
                        'disabled': 0,
                        'enabled': 1,
                        'static': 2,
                        'indirect': 3,
                "Condition": 
                        'no': 0,
                        'start': 1
        """)
        sys.exit()
    if len(sys.argv) == 2:
        # TODO: check service name
        service_name = sys.argv[1]
    if not allowed_service_name(service_name):
        print("Not allowed service name")
        sys.exit()
    main(service_name)
