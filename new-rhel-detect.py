##############################################
# This script is used to detect new RHEL build
# and run avocado-azure automatically.
##############################################

#!/usr/bin/python

import os
import re
import commands
import time
import smtplib
from email.mime.text import MIMEText
from email.header import Header

PYTHON = "/usr/bin/python"
AVOCADO_AZURE = os.path.split(os.path.realpath(__file__))[0]
SCRIPT = "%s/tools/azure_image_prepare/azure_image_prepare.py" % AVOCADO_AZURE
LOG = "/tmp/new-rhel-detach.log"
PREFIX = time.strftime("[%Y-%m-%d %H:%M:%S]", time.localtime())

def log(msg):
    with open(LOG,'a') as f:
        f.write("%s %s\n" % (PREFIX, msg))

def run(cmd):
    status, output = commands.getstatusoutput(cmd)
    return output

def config():
    avocado_conf = '/etc/avocado/avocado.conf'
    comp_test = re.compile('^test_dir = .*$')
    comp_data = re.compile('^data_dir = .*$')
    comp_logs = re.compile('^logs_dir = .*$')
    with open(avocado_conf, 'r') as f:
        data = f.readlines()
    new_data = ""
    for line in data:
        if re.findall(comp_test, line):
            line = "test_dir = %s/tests\n" % AVOCADO_AZURE
        elif re.findall(comp_data, line):
            line = "data_dir = %s/data\n" % AVOCADO_AZURE
        elif re.findall(comp_logs, line):
            line = "logs_dir = %s/job-results\n" % AVOCADO_AZURE
        new_data += line
    with open(avocado_conf, 'w') as f:
        f.write(new_data)

def sendmail(build):
    sender = 'xintest@redhat.com'
    receivers = ['yuxisun@redhat.com']  
    message = MIMEText('There\'s a new RHEL build %s. Run avocado-azure.' % build, 'plain')
    message['From'] = Header(sender)
    message['To'] =  Header(';'.join(receivers))
    message['Subject'] = Header('New Build Notification')
    try:
        smtpObj = smtplib.SMTP('localhost')
        smtpObj.sendmail(sender, receivers, message.as_string())
        log("Send mail successfully.")
    except smtplib.SMTPException:
        log("Cannot send mail.")

def main():
    latest_build=run("%s %s -rhelbuild" % (PYTHON, SCRIPT))
    local_build=run("%s %s -localbuild" % (PYTHON, SCRIPT))
    if latest_build == local_build:
        log("No new build")
    else:
        log("Have new build: $latest_build")
        config()
        os.chdir(AVOCADO_AZURE)
        run("%s run.py &" % PYTHON)
        sendmail(latest_build)

if __name__ == "__main__":
    main()