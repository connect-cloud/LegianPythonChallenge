#!/usr/bin/env python
""" This script is written for the Legian Python challenge (beginners challenge).
The script connects to the devices specified in the device inventory file and executes a couple of show commands,
the output of the show commands is saved in plain text files.
Additional to the requirements of the challenge,
this script has the ability to connect to devices via a jumphost server. This functionality is added because I needed it
to test the script in the network of a customer I'm working.

To get the script running configure the script parameters in the 'script_parameters.conf' file
The show commands can be defined in the 'device_type_parameters.json' JSON file.
(this is configured per device type because some devices use different commands for the same kind of output)
The devices can be defined in the 'device_inventory.json' JSON file.

"""

import json
import time
import logging
import configparser

from netmiko import ConnectHandler
from netmiko import redispatch

__author__ = "Bart Nijssen"
__copyright__ = "Copyright 2022, Bart Nijssen"
__license__ = "GPL"
__version__ = "1.0"
__maintainer__ = "Bart Nijssen"
__email__ = "b.nijssen@legian.nl"
__status__ = "Production ready"


def get_device_info(device: dict, device_type_params: dict, jumphost_params: dict,
                    device_connect_credentials: dict):
    """ Connect to the device, execute the show commands and return the result of the command
    :param device: dict of device parameters. e.g. hostname/ip and type
    :param device_type_params: dict of device type paramers. e.g. initial commands and specific show commands
    :param jumphost_params: dict of parameters to connect to the jumhost
    :param device_connect_credentials: dict of credentials to connect to the devices
    :return: list of outputs of the show commands
    """
    if jumphost_params['host']:  # If a jump host hostname or IP is added it will connect via the jump host
        logging.debug(f"Jumphost parameters are filled so use jumphost to connect to device")
        connect_params = {
            'device_type': jumphost_params['device_type'],
            'host': jumphost_params['host'],
            'username': jumphost_params['username'],
            'password': jumphost_params['password'],
        }
        net_connect = ConnectHandler(**connect_params)
        net_connect.find_prompt()
        logging.info(f"Connected to jumphost {jumphost_params['host']} for device {device['host']}")
        net_connect.write_channel(f"ssh {device_connect_credentials['username']}@{device['host']}\n")
        time.sleep(1)
        output = net_connect.read_channel()
        if any(x in output for x in ['password', 'Password']):
            logging.info(f"Connecting to device and found password prompt for {device['host']}")
            net_connect.write_channel(f"{device_connect_credentials['password']}\n")
        net_connect.find_prompt()  # Only continue if the prompt is available
        redispatch(net_connect, device_type=device['type'])
        logging.info(f"Connected and redispatched to device  {device['host']}")

    else:
        # Directly connect to the device if jump host is not configured
        connect_params = {
            'device_type': device['type'],
            'host': device['host'],
            'username': device_connect_credentials['username'],
            'password': device_connect_credentials['password'],
        }
        net_connect = ConnectHandler(**connect_params)
        net_connect.find_prompt()
        logging.info(f"Connected to device  {device['host']}")

    # Send initial commands to the device
    for command in device_type_params['initial_commands']:
        net_connect.send_command(command)  # send error to logging and quit if not possible

    # Create a list of
    output = []
    for command in device_type_params['show_commands']:
        output.append(net_connect.send_command(command, use_textfsm=False))

    net_connect.disconnect()  # Disconnect from the router so the SSH session is closed
    logging.info(f"Disconnected from {device['host']}")
    return output


def main():
    # Read script parameter file
    script_parameters = configparser.ConfigParser()
    script_parameters.read('script_parameters.conf')
    jumphost_params = dict(script_parameters['jumphost'])
    device_connect_credentials = dict(script_parameters['device_connect_credentials'])

    # Configure logging
    log_level_info = {'logging.DEBUG': logging.DEBUG,
                      'logging.INFO': logging.INFO,
                      'logging.WARNING': logging.WARNING,
                      'logging.ERROR': logging.ERROR,
                      }

    logging.basicConfig(level=log_level_info.get(script_parameters['logging']['loglevel'], logging.ERROR),
                        filename=script_parameters['logging']['logfile'],
                        format="%(asctime)s - %(levelname)s - %(module)s - %(name)s - Line %(lineno)d - %(message)s"
                        )

    # Read device parameter file
    with open('device_inventory.json', 'r') as f:
        devices = json.load(f)

    # Read device type parameter file
    with open('device_type_parameters.json', 'r') as f:
        device_type_parameters = json.load(f)

    # Get the device info and write to file
    for device in devices:
        device_type_params = device_type_parameters[device['type']]
        current_time = time.strftime("%Y-%m-%d_%H%M%S")
        filename = f"{device['hostname']}_{current_time}.txt"
        with open(filename, 'w') as f:
            show_command_outputs = get_device_info(device,
                                                   device_type_params,
                                                   jumphost_params,
                                                   device_connect_credentials)
            for output in show_command_outputs:
                f.write(output)


if __name__ == '__main__':
    main()
