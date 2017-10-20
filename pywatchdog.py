#!/usr/bin/env python

"""
This is a 'Watch Dog' utility, it will take an SysV Linux style service name
and make sure it is up and running. If for some reason it's not, it will
attempt to start it up to a user defined number of times and then give up.

Email alrets are supported.

Run:

$ pywatchdog.py --help 
To get started with usage examples and list of possible command line arguments.

Copyright (C) 2016 Sivan Greenberg, released under GPLv3
"""

import os
import sys
import argparse
import logging
import demonize
import time
import subprocess
import requests


# SysV Inint Style as per the Linux Standard (also adhered by Upstart)
SERVICE_COMMAND = 'service'
STATUS_COMMAND = 'status'
START_COMMAND = 'restart'
EMAIL_FROM = 'noreply-alerts@example.com'
PID_FILE = 'pywatchdog.pid'

_log = logging.getLogger('pywatchdog')

MAILGUN = {}

# Fill these with your own, after creating an account with awesome mailgun.
MAILGUN['key'] = 'key-'
MAILGUN['sandbox'] = '.mailgun.org'
MAILGUN['from'] = EMAIL_FROM

def mailgun(message, recipient):
    """
    Send %message using mailgun
    """
    from socket import getfqdn
    request_url = 'https://api.mailgun.net/v2/{0}/messages'.format(MAILGUN['sandbox'])
    request = requests.post(request_url, auth=('api', MAILGUN['key']), data={
        'from': MAILGUN['from'],
        'to': recipient,
        'subject': "Alert from {0}".format(getfqdn()), 
        'text': message})

    _log.debug('Mail send status: {0}'.format(request.status_code))
    _log.debug('Body:             {0}'.format(request.text))



def is_running(service_name):
    """
    Finds out if %service_name is running.
    """
    from subprocess import Popen
    output = Popen([SERVICE_COMMAND, 
                    service_name, STATUS_COMMAND], 
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE).communicate()
    if output[1]!='':
        _log.info(output[1])
        sys.exit(1)
    elif 'running' in output[0]:
        return True
    else:
        return False

def start(service_name):
    from subprocess import Popen
    return(
        Popen([SERVICE_COMMAND, service_name, START_COMMAND]).wait()
        )
    

def watch(service_name, max_restart, interval, notifywho):
    """
    Implements watch main loop per %service_name
    """
    restart_count = 0
    while True:
        time.sleep(interval)
        if is_running(service_name):
            _log.debug("Service %s is running." % service_name)
        else:
            _log.info("Service %s is down." % service_name)
	    restart_count += 1
            if restart_count < max_restart:
                _log.debug("Starting %s." % service_name)
                exit_value = start(service_name)
                if exit_value!=0:
                    _log.info("Starting %s failed with exit code=%s" % (service_name, exit_value))
                else:
                    _log.info(
                    "Service %service_name has been restarted after %s attempts."  % (
                        service_name, restart_count))
                    mailgun("Service %s has been started after %s attempts." % (
                        service_name, restart_count), notifywho)
                    restart_count = 0
    
            else:
                _log.info("Service %s can't be started after %s attempts." % ( 
                        service_name , restart_count))
                mailgun("Service %s can't be started after %s attempts." % (service_name, max_restart),
                            notifywho)
                sys.exit(1) # indicate unix error


def _parse_args():
    """
    Parse command line args
    """
    p = argparse.ArgumentParser(description="Python Watchdog: ensure service is up.")
    p.add_argument('--service-name', '-n', required=True, action='store' ,
                    help="Specify service name to watchdog (Look at /etc/init.d for avail. services")
    p.add_argument('--interval', '-i', action='store', required=False, default=5,
                    help='Watchdog interval in seconds, default: 5secs')
    p.add_argument('--debug', action='store_true',  required=False, default=False,
                    help='output verbose information')
    p.add_argument('--daemonize', action='store_true', required=False, default=False,
                    help='Make this watchdog a daemon, e.g. detach to background to keep watching!')
    p.add_argument('--max-restart', '-m', action='store', required=False, default=5,
                    help='How many times to try restarting before giving up.')
    p.add_argument('--alert-email', '-e', action='store', required=True, default='yourname@example.com',
                    help='Email address to send service operation alerts.')
    p.add_argument('--log-file', '-l', action='store', required=False, default=None,
                    help='Log operations to file.')
    return p.parse_args()


def main():
    """
    Main function
    """
    from subprocess import Popen
    args = _parse_args()

    log_foramt = '%(asctime)-15s %(name)-15s %(levelname)s %(message)s'


    if args.log_file!=None:
        logging.basicConfig(format=log_foramt,
                            filename=args.log_file,
                            level=logging.INFO
                        )
    else:
        logging.basicConfig(format=log_foramt,
                            level=logging.INFO
                        )
            
    if args.debug:
        logging.root.setLevel(logging.DEBUG)

    if 'unrecognized' in Popen(
                [SERVICE_COMMAND, args.service_name, STATUS_COMMAND], 
                            stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE).communicate()[1]:
        _log.info("Service %s is not recognized." % args.service_name)
        sys.exit(1)
 

    if args.daemonize:
        demonize.demonize(PID_FILE, watch, args.service_name, args.max_restart,
                            args.interval, args.alert_email)
    else:
       watch(args.service_name, 
            args.max_restart, args.interval , args.alert_email)
        

if __name__ == "__main__":
    sys.exit(main())
