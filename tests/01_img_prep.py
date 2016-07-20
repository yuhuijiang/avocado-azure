import time

from avocado import Test
from avocado import main

import sys
import os
#sys.path.append(os.path.split(os.path.realpath("__file__"))[0] + "/..")
sys.path.append(sys.path[0].replace("/tests", ""))
from azuretest import azure_cli_common
from azuretest import azure_asm_vm
from azuretest import azure_arm_vm
from azuretest import azure_image
#from azuretest import utils_misc


def collect_vm_params(params):
    return


class ImgPrepTest(Test):

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
#        azure_cli_common.set_config_mode(self.azure_mode)

        # 1. Source
        # Set azure mode to ASM mode. Source storage account is classic
        azure_cli_common.set_config_mode("asm")
        # Prepare the storage account instance
        self.sto_src_params = dict()
        self.sto_src_params["name"] = self.params.get('name', '*/Prepare/storage_account/*')
        self.sto_src_params["location"] = self.params.get('location', '*/Prepare/storage_account/*')
        self.sto_src_params["type"] = self.params.get('type', '*/Prepare/storage_account/*')
        self.sto_src_test01 = azure_asm_vm.StorageAccount(name=self.sto_src_params["name"],
                                                          params=self.sto_src_params)
        # Create storage account
        if not self.sto_src_test01.check_exist():
            self.sto_src_test01.create(self.sto_src_params)
        # Prepare the container instance
        self.container_src_params = dict()
        self.container_src_params["name"] = self.params.get('container', '*/Prepare/*')
        self.container_src_params["storage_account"] = self.sto_src_params["name"]
        self.container_src_test01 = azure_asm_vm.Container(name=self.container_src_params["name"],
                                                           storage_account=self.container_src_params["storage_account"],
                                                           params=self.container_src_params)
        # Create container
        if not self.container_src_test01.check_exist():
            self.container_src_test01.create(self.container_src_params)
        # Prepare the blob instance
        self.blob_params = dict()
        self.blob_params["name"] = self.params.get('name', '*/DiskBlob/*')
        self.blob_params["container"] = self.container_src_params["name"]
        self.blob_params["storage_account"] = self.sto_src_params["name"]
        self.blob_test01 = azure_asm_vm.Blob(name=self.blob_params["name"],
                                             container=self.blob_params["container"],
                                             storage_account=self.blob_params["storage_account"],
                                             params=self.blob_params)
        self.vhd_file = self.params.get('vhd_file_path', '*/Prepare/*') + self.blob_params["name"]
        self.log.debug("VHD file fullpath: %s" % self.vhd_file)
        self.no_upload = False
        if self.blob_test01.check_exist():
            self.no_upload = True
            if "prepare_image" in self.name.name or \
               "convert_image" in self.name.name:
                self.skip("VHD blob already exists. Skip this case")
        # 2. Destination
        # Set azure mode follow the configuration
        azure_cli_common.set_config_mode(self.azure_mode)
        # Prepare the storage account instance
        self.sto_dst_params = dict()
        self.sto_dst_params["name"] = self.params.get('storage_account', '*/resourceGroup/*')
        self.sto_dst_params["location"] = self.params.get('location', '*/resourceGroup/*')
        self.sto_dst_params["type"] = self.params.get('storage_account_type', '*/resourceGroup/*')
        if self.azure_mode == "asm":
            self.sto_dst_test01 = azure_asm_vm.StorageAccount(name=self.sto_dst_params["name"],
                                                              params=self.sto_dst_params)
        else:
            self.sto_dst_params["ResourceGroupName"] = self.params.get('rg_name', '*/resourceGroup/*')
            self.sto_dst_test01 = azure_arm_vm.StorageAccount(name=self.sto_dst_params["name"],
                                                              params=self.sto_dst_params)
        # Create storage account
        if not self.sto_dst_test01.check_exist():
            self.sto_dst_test01.create(self.sto_dst_params)
        self.dst_connection_string = self.sto_dst_test01.conn_show()
        self.log.debug("self.dst_connection_string=%s" % self.dst_connection_string)
        # Prepare the container instance
        self.container_dst_params = dict()
        self.container_dst_params["name"] = self.params.get('container', '*/resourceGroup/*')
        self.container_dst_params["storage_account"] = self.sto_dst_params["name"]
        if self.azure_mode == "asm":
            self.container_dst_test01 = azure_asm_vm.Container(name=self.container_dst_params["name"],
                                                               storage_account=self.container_dst_params["storage_account"],
                                                               params=self.container_dst_params)
        else:
            self.container_dst_params["ResourceGroupName"] = self.params.get('rg_name', '*/resourceGroup/*')
            self.container_dst_test01 = azure_arm_vm.Container(name=self.container_dst_params["name"],
                                                               storage_account=self.container_dst_params["storage_account"],
                                                               params=self.container_dst_params)
        # Create container
        if not self.container_dst_test01.check_exist():
            self.container_dst_test01.create(self.container_dst_params)
        # Prepare the Image instance (Only for asm mode)
        if self.azure_mode == "asm":
            self.image_params = dict()
            self.image_params["name"] = self.params.get('name', '*/Image/*')
            self.image_params["blob_url"] = "https://%s.blob.core.windows.net/%s/%s" % \
                                            (self.sto_dst_params["name"],
                                             self.container_dst_params["name"],
                                             self.blob_params["name"])
            self.image_params["location"] = self.sto_dst_params["location"]
            self.image_test01 = azure_asm_vm.Image(name=self.image_params["name"],
                                                   params=self.image_params)
            if self.image_test01.check_exist():
                self.image_test01.delete()
#                self.skip("Image already exists. Skip all the Image Preparation cases.")

    def test_01_prepare_image(self):
        """
        Install an image from iso
        """
        realpath = os.path.split(os.path.realpath(__file__))[0]
        cmd = "/usr/bin/python %s/../tools/azure_image_prepare/azure_image_prepare.py -setup" % realpath
        self.assertEqual(azure_cli_common.host_command(cmd, ret='exit_status'), 0,
                         "Fail to setup environment")
        self.log.info("Begin to install image")
        cmd = "/usr/bin/python %s/../tools/azure_image_prepare/azure_image_prepare.py -check" % realpath
        self.assertEqual(azure_cli_common.host_command(cmd, ret='exit_status'), 0,
                         "Fail to check environment")
        cmd = "/usr/bin/python %s/../tools/azure_image_prepare/azure_image_prepare.py -download" % realpath
        self.assertEqual(azure_cli_common.host_command(cmd, ret='exit_status', timeout=12*3600), 0,
                         "Fail to download iso")
        cmd = "/usr/bin/python %s/../tools/azure_image_prepare/azure_image_prepare.py -install" % realpath
        self.assertEqual(azure_cli_common.host_command(cmd, ret='exit_status', timeout=12*3600), 0,
                         "Fail to install image")

    def test_02_convert_image(self):
        """
        Convert qcow2 image to vhd format
        """
        realpath = os.path.split(os.path.realpath(__file__))[0]
        cmd = "/usr/bin/python %s/../tools/azure_image_prepare/azure_image_prepare.py -convert" % realpath
        self.assertEqual(azure_cli_common.host_command(cmd, ret='exit_status'), 0,
                         "Fail to check image")

    def test_03_import_image_to_azure(self):
        """
        1. Upload vhd file to Azure Storage
        2. Copy the vhd to the specific storage account
        3. Create an image base on the vhd
        """
        self.log.info("Import the image to Azure")
        self.log.info("Use ASM mode azure cli commands")
        azure_cli_common.set_config_mode("asm")
        # 1. Upload vhd file to Azure Storage
        # 1.1 Check if vhd blob already exists
        if self.no_upload:
            self.log.info("The vhd blob already exists. Will not upload the vhd.")
        else:
            # 1.2 If doesn't exist, upload vhd to azure
            self.log.info("Begin to upload the vhd")
            self.assertEqual(self.blob_test01.upload(self.vhd_file, self.blob_params), 0,
                             "Fail to upload the VHD file %s to storage account %s container %s" %
                             (self.vhd_file, self.blob_params["storage_account"], self.blob_params["container"]))
            self.log.info("Upload %s to Azure Storage %s Container %s successfully" %
                          (self.vhd_file, self.blob_params["storage_account"], self.blob_params["container"]))
        # 2. Copy the vhd to the specific storage account
        self.assertTrue(self.blob_test01.copy(self.dst_connection_string),
                        "Fail to copy the VHD file %s to storage account %s container %s" %
                        (self.vhd_file, self.sto_dst_params["name"], self.blob_params["container"]))
        # 3. Create an image base on the vhd (only for asm mode)
        if self.azure_mode == "asm":
            self.assertEqual(self.image_test01.create(self.image_params), 0,
                             "Fail to create vm image %s" % self.image_params["name"])

    def tearDown(self):
        self.log.debug("Teardown.")
        return

if __name__ == "__main__":
    main()