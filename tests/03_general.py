import time

from avocado import Test
from avocado import main

import sys
import os
import copy

#sys.path.append(os.path.split(os.path.realpath("__file__"))[0] + "/..")
sys.path.append(sys.path[0].replace("/tests", ""))
from azuretest import azure_cli_common
from azuretest import azure_asm_vm
from azuretest import azure_arm_vm
from azuretest import azure_image


def collect_vm_params(params):
    return


class GeneralTest(Test):
    def setUp(self):
        # Get azure mode and choose test cases
        self.azure_mode = self.params.get('azure_mode', '*/azure_mode/*')
        self.log.debug("AZURE_MODE: %s", self.azure_mode)
        if self.name.name.split(':')[-1] not in self.params.get('cases', '*/azure_mode/*'):
            self.skip("Skip case %s in Azure Mode %s" % (self.name.name, self.azure_mode))
        # Login Azure and change the mode
        self.azure_username = self.params.get('username', '*/AzureSub/*')
        self.azure_password = self.params.get('password', '*/AzureSub/*')
        azure_cli_common.login_azure(username=self.azure_username,
                                     password=self.azure_password)
        azure_cli_common.set_config_mode(self.azure_mode)

        # Prepare the vm parameters and create a vm
        self.vm_params = dict()
        self.vm_params["username"] = self.params.get('username', '*/VMUser/*')
        self.vm_params["password"] = self.params.get('password', '*/VMUser/*')
        self.vm_params["VMSize"] = self.params.get('vm_size', '*/azure_mode/*')
        self.vm_params["VMName"] = self.params.get('vm_name', '*/azure_mode/*')
        self.vm_params["VMName"] += self.vm_params["VMSize"].split('_')[-1].lower()
        self.vm_params["Location"] = self.params.get('location', '*/resourceGroup/*')
        self.vm_params["region"] = self.params.get('region', '*/resourceGroup/*')
        self.vm_params["StorageAccountName"] = self.params.get('storage_account', '*/resourceGroup/*')
        self.vm_params["Container"] = self.params.get('container', '*/resourceGroup/*')
        self.vm_params["DiskBlobName"] = self.params.get('name', '*/DiskBlob/*')
        self.vm_params["PublicPort"] = self.params.get('public_port', '*/network/*')
        if "check_sshkey" in self.name.name:
            self.vm_params["VMName"] += "key"
            self.vm_params["password"] = None
            self.host_pubkey_file = azure_cli_common.get_sshkey_file()
            self.vm_params["ssh_key"] = self.host_pubkey_file
        if self.azure_mode == "asm":
            self.vm_params["Image"] = self.params.get('name', '*/Image/*')
            self.vm_params["DNSName"] = self.vm_params["VMName"] + ".cloudapp.net"
            self.vm_test01 = azure_asm_vm.VMASM(self.vm_params["VMName"],
                                                self.vm_params["VMSize"],
                                                self.vm_params["username"],
                                                self.vm_params["password"],
                                                self.vm_params)
        else:
            self.vm_params["DNSName"] = self.vm_params["VMName"] + "." + self.vm_params[
                "region"] + ".cloudapp.azure.com"
            self.vm_params["ResourceGroupName"] = self.params.get('rg_name', '*/resourceGroup/*')
            self.vm_params["URN"] = "https://%s.blob.core.windows.net/%s/%s" % (self.vm_params["StorageAccountName"],
                                                                                self.vm_params["Container"],
                                                                                self.vm_params["DiskBlobName"])
            self.vm_params["NicName"] = self.vm_params["VMName"]
            self.vm_params["PublicIpName"] = self.vm_params["VMName"]
            self.vm_params["PublicIpDomainName"] = self.vm_params["VMName"]
            self.vm_params["VnetName"] = self.vm_params["VMName"]
            self.vm_params["VnetSubnetName"] = self.vm_params["VMName"]
            self.vm_params["VnetAddressPrefix"] = self.params.get('vnet_address_prefix', '*/network/*')
            self.vm_params["VnetSubnetAddressPrefix"] = self.params.get('vnet_subnet_address_prefix', '*/network/*')
            self.vm_test01 = azure_arm_vm.VMARM(self.vm_params["VMName"],
                                                self.vm_params["VMSize"],
                                                self.vm_params["username"],
                                                self.vm_params["password"],
                                                self.vm_params)
        self.log.debug("Create the vm %s", self.vm_params["VMName"])
        # If vm doesn't exist, create it. If it exists, start it.
        self.vm_test01.vm_update()
        if not self.vm_test01.exists():
            self.vm_test01.vm_create(self.vm_params)
            self.vm_test01.wait_for_running()
        else:
            if not self.vm_test01.is_running():
                self.vm_test01.start()
                self.vm_test01.wait_for_running()
        if "check_sshkey" in self.name.name:
            self.log.debug("Case name is check_sshkey. Don't verify alive during setUp.")
            return
        if not self.vm_test01.verify_alive():
            self.error("VM %s is not available. Exit." % self.vm_params["VMName"])
        #        self.project = float(self.vm_test01.get_output("cat /etc/redhat-release|awk '{print $7}'", sudo=False))
        self.project = self.params.get('Project', '*/Common/*')
        self.conf_file = "/etc/waagent.conf"
        # Increase sudo password timeout
        self.vm_test01.modify_value("Defaults timestamp_timeout", "-1", "/etc/sudoers", "=")

    def test_check_release_version(self):
        """
        Check the /etc/redhat-release file contains a correct release version
        """
        self.log.info("Check the /etc/redhat-release file contains a correct release version")
        output_version = self.vm_test01.get_output("cat /etc/redhat-release")
        self.assertIn(str(self.project), output_version,
                      "Wrong version in /etc/redhat-release file. Real version: %s" % output_version)

    def test_check_boot_messages(self):
        """
        Check if there's error in the /var/log/messages file
        """
        self.log.info("Check the boot messages")
        # The ignore_list must not be empty
        ignore_list = ["failed to get extended button data",
                       "Starting kdump: [FAILED]",
                       "kdump.service: main process exited, code=exited, status=1/FAILURE",
                       "Failed to start Crash recovery kernel arming.",
                       "Unit kdump.service entered failed state.",
                       "kdump.service failed.",
                       "kdumpctl: Starting kdump: [FAILED]"
                       "acpi PNP0A03:00: _OSC failed (AE_NOT_FOUND); disabling ASPM",
                       "acpi PNP0A03:00: fail to add MMCONFIG information, can't access extended PCI configuration space under this bridge.",
                       "Dependency failed for Network Manager Wait Online.",
                       "Job NetworkManager-wait-online.service/start failed with result 'dependency'",
                       "rngd.service: main process exited, code=exited, status=1/FAILURE",
                       "Unit rngd.service entered failed state",
                       "rngd.service failed"]
        ignore_msg = '|'.join(ignore_list)
        cmd = "cat /var/log/messages | grep -iE 'error|fail' | grep -vE '%s'" % ignore_msg
        error_log = self.vm_test01.get_output(cmd)
        self.assertEqual(error_log, "", "There's error in the /var/log/messages: \n%s" % error_log)

    def test_check_hostname(self):
        """
        Check if the hostname is which we set
        """
        self.log.info("Check the hostname")
        self.assertEqual(self.vm_test01.get_output("hostname"), self.vm_test01.name,
                         "Hostname is not the one which we set")

    def test_check_account(self):
        """
        Check if the new account created during provisioning works well
        """
        self.log.info("Check the new account created by WALinuxAgent")
        self.assertIn(self.vm_test01.username, self.vm_test01.get_output("cat /etc/sudoers.d/waagent"),
                      "The new account is not in the sudo list.")

    def test_check_sshkey(self):
        """
        Check if can access to the VM with ssh key
        """
        self.log.info("Access the VM with the ssh key")
        self.assertTrue(self.vm_test01.verify_alive(timeout=120, authentication="publickey"),
                        "Fail to login with ssh_key.")
        self.assertIn("NOPASSWD", self.vm_test01.get_output("cat /etc/sudoers.d/waagent"),
                      "It should be NOPASSWD in /etc/sudoers.d/waagent")
        self.assertTrue(self.vm_test01.verify_value("PasswordAuthentication", "no", "/etc/ssh/sshd_config", ' '),
                        "PasswordAuthentication should be no in sshd_config")

    def test_check_waagent_log(self):
        """
        Check if there's error logs in /var/log/waagent.log
        """
        self.log.info("Check the waagent log")
        if "python /usr/sbin/waagent -daemon" not in self.vm_test01.get_output("ps aux|grep [w]aagent"):
            self.vm_test01.get_output("service waagent start")
        # The ignore_list must not be empty.
        ignore_list = ["install-rhui-rpm.sh does not exist",
                       "Error Code is 255",
                       "Command string was swapon /mnt/resource/swapfile",
                       "Command result was swapon: /mnt/resource/swapfile: swapon failed: Device or resource busy",
                       "Failed to activate swap at /mnt/resource/swapfile"]
        ignore_msg = '|'.join(ignore_list)
        cmd = "cat /var/log/waagent.log | grep -iE 'error|fail' | grep -vE '%s'" % ignore_msg
        error_log = self.vm_test01.get_output(cmd)
        self.assertEqual(error_log, "", "There's error in the /var/log/waagent.log: \n%s" % error_log)

    def test_verify_package_signed(self):
        """
        Check if the WALinuxAgent package is signed
        """
        self.log.info("Verify all packages are signed")
        self.vm_test01.get_output("rm -f /etc/yum.repos.d/redhat.repo")
        self.vm_test01.get_output("rpm -ivh /root/RHEL*.rpm")
        self.assertIn("rh-cloud.repo", self.vm_test01.get_output("ls /etc/yum.repos.d/"),
                      "RHUI is not installed. Cannot use yum.")
        self.vm_test01.get_output("rpm -e WALinuxAgent")
        self.vm_test01.get_output("yum install WALinuxAgent -y")
        cmd = "rpm -q WALinuxAgent --qf '%{name}-%{version}-%{release}.%{arch} (%{SIGPGP:pgpsig})';echo"
        self.assertIn("Key ID", self.vm_test01.get_output(cmd),
                      "Fail to verify WALinuxAgent package signature")

    def test_check_waagent_service(self):
        """
        Verify waagent service commands
        """
        self.log.info("Check the waagent service")
        # 1. service waagent start
        self.vm_test01.get_output("service waagent stop")
        self.assertNotIn("FAILED", self.vm_test01.get_output("service waagent start"),
                         "Fail to start waagent: command fail")
        time.sleep(3)
        self.assertIn("python /usr/sbin/waagent -daemon", self.vm_test01.get_output("ps aux|grep waagent"),
                      "Fail to start waagent: result fail")
        # 2. service waagent restart
        old_pid = self.vm_test01.get_output("ps aux|grep [w]aagent|awk '{print \$2}'")
        self.assertNotIn("FAILED", self.vm_test01.get_output("service waagent restart"),
                         "Fail to restart waagent: command fail")
        self.assertIn("python /usr/sbin/waagent -daemon", self.vm_test01.get_output("ps aux|grep waagent"),
                      "Fail to restart waagent: cannot start waagent service")
        new_pid = self.vm_test01.get_output("ps aux|grep [w]aagent|awk '{print \$2}'")
        self.assertNotEqual(old_pid, new_pid,
                            "Fail to restart waagent: service is not restarted")
        # 3. kill waagent -daemon then start
        self.vm_test01.get_output("ps aux|grep [w]aagent|awk '{print \$2}'|xargs kill -9")
        if float(self.project) < 7.0:
            self.assertEqual("waagent dead but pid file exists", self.vm_test01.get_output("service waagent status"),
                             "waagent service status is wrong after killing process")
        else:
            self.assertIn("code=killed, signal=KILL", self.vm_test01.get_output("service waagent status"),
                          "waagent service status is wrong after killing process")
        self.assertNotIn("FAILED", self.vm_test01.get_output("service waagent start"),
                         "Fail to start waagent after killing process: command fail")
        self.assertIn("running", self.vm_test01.get_output("service waagent status"),
                      "waagent service status is not running.")
        self.assertIn("python /usr/sbin/waagent -daemon", self.vm_test01.get_output("ps aux|grep waagent"),
                      "Fail to start waagent after killing process: result fail")

    def test_start_waagent_repeatedly(self):
        """
        If start waagent service repeatedly, check if there's only one waagent process
        """
        self.log.info("Start waagent service repeatedly")
        self.vm_test01.get_output("service waagent start")
        self.vm_test01.get_output("service waagent start")
        waagent_count = self.vm_test01.get_output("ps aux|grep [w]aagent|wc -l")
        self.assertEqual(waagent_count, "1",
                         "There's more than 1 waagent process. Actually: %s" % waagent_count)

    def test_check_hyperv_modules(self):
        """
        Check the hyper-V modules
        """
        self.log.info("Check the hyper-v modules")
        module_list = ["hv_utils", "hv_netvsc", "hid_hyperv", "hyperv_keyboard",
                       "hv_storvsc", "hyperv_fb", "hv_vmbus"]
        output = self.vm_test01.get_output("lsmod|grep -E 'hv|hyperv'")
        for module in module_list:
            self.assertIn(module, output,
                          "%s module doesn't exist" % module)

    def test_install_uninstall_wala(self):
        """
        Check if can install and uninstall wala package through rpm and yum
        """
        self.log.info("Installing and Uninstalling the WALinuxAgent package")
        # 1.1 rpm -ivh WALinuxAgent*.rpm
        self.log.info("The install WALinuxAgent*.rpm step is done during preparation. Skip step 1.1.")
        # 1.2. rpm -e WALinuxAgent
        self.vm_test01.get_output("rpm -e WALinuxAgent")
        self.assertIn("No such file", self.vm_test01.get_output("ls /usr/sbin/waagent"),
                      "Fail to remove WALinuxAgent package")
        # 2.1 yum install WALinuxAgent
        self.vm_test01.get_output("rm -f /etc/yum.repos.d/redhat.repo")
        self.vm_test01.get_output("rpm -ivh /root/RHEL*.rpm")
        time.sleep(1)
        self.assertIn("rh-cloud.repo", self.vm_test01.get_output("ls /etc/yum.repos.d/"),
                      "RHUI is not installed. Cannot use yum.")
        self.vm_test01.get_output("yum install WALinuxAgent -y")
        self.assertNotIn("No such file", self.vm_test01.get_output("ls /usr/sbin/waagent"),
                         "Fail to install WALinuxAgent through yum")
        # 2.2 yum remove WALinuxAgent
        self.vm_test01.get_output("yum remove WALinuxAgent -y")
        self.assertIn("No such file", self.vm_test01.get_output("ls /usr/sbin/waagent"),
                      "Fail to remove WALinuxAgent through yum")

    def tearDown(self):
        self.log.debug("tearDown")
        if ("check_sshkey" in self.name.name) or \
           ("install_uninstall_wala" in self.name.name) or \
           ("verify_package_signed" in self.name.name):
            self.vm_test01.delete()
            self.vm_test01.wait_for_delete()
        if ("start_waagent_repeatedly" in self.name.name) or \
           ("check_waagent_service" in self.name.name):
            self.vm_test01.waagent_service_stop()
            if not self.vm_test01.waagent_service_start():
                self.vm_test01.delete()
                self.vm_test01.wait_for_delete()


if __name__ == "__main__":
    main()