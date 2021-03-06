#coding=utf-8
from __future__ import print_function
import unittest
import time

from sys import version_info
IS_PY3 = version_info[0] >= 3

if IS_PY3:
  from urllib.request import urlopen
else:
  from urllib2 import urlopen

import hashlib

import sys
sys.path.append('../')
import os
from os.path import expanduser

from fds.auth import Common
from fds.galaxy_fds_client import GalaxyFDSClient
from fds.galaxy_fds_client_exception import GalaxyFDSClientException
from fds.fds_client_configuration import FDSClientConfiguration
from fds.model.fds_object_metadata import FDSObjectMetadata
from fds.model.permission import Permission
from fds.model.permission import AccessControlList
from fds.model.permission import Grant
from fds.model.permission import Grantee
from fds.model.upload_part_result_list import UploadPartResultList
import json

from test.test_common import *
from datetime import datetime

class ClientTest(unittest.TestCase):
  @classmethod
  def setUpClass(cls):
    ClientTest.init_from_local_config()
    config = FDSClientConfiguration(
      region_name=region_name,
      enable_https=False,
      enable_cdn_for_upload=False,
      enable_cdn_for_download=False,
      endpoint=endpoint)
    config.enable_md5_calculate = True
    ClientTest.client = GalaxyFDSClient(access_key, access_secret, config)
    ClientTest.bucket_name = 'test-python-' + datetime.strftime(datetime.now(), "%Y%m%d%H%M%S%z")
    ClientTest.delete_objects_and_bucket(cls.client, cls.bucket_name)
    ClientTest.client.create_bucket(cls.bucket_name)

  @classmethod
  def tearDownClass(cls):
    ClientTest.delete_objects_and_bucket(ClientTest.client, ClientTest.bucket_name)

  @staticmethod
  def delete_objects_and_bucket(client, bucket_name):
    if client.does_bucket_exist(bucket_name):
      for obj in client.list_all_objects(bucket_name):
        client.delete_object(bucket_name, obj.object_name)
      client.delete_bucket(bucket_name)

  @staticmethod
  def init_from_local_config():
    global access_key, access_secret, endpoint
    if type(access_key) == str and access_key.strip() != "":
      return
    config_dirs = [os.path.join(expanduser("~"), ".config", "xiaomi", "config"),
      os.path.join(expanduser("~"), ".config", "fds", "client.config")];
    config = {}
    for config_dir in config_dirs:
      if not os.path.exists(config_dir):
        pass
      else:
        with open(config_dir) as f:
          config = json.load(fp=f)
    access_key = config.get("xiaomi_access_key_id", "")
    access_secret = config.get("xiaomi_secret_access_key", "")
    endpoint = config.get("xiaomi_fds_endpoint", "")

  def test_set_endpoint(self):
    httpConfig = FDSClientConfiguration(region_name, False, False, False)
    endpoint = region_name + ".api.xiaomi.net"
    httpConfig.set_endpoint(endpoint)
    httpUri = httpConfig.get_base_uri()
    self.assertEqual("http://" + endpoint + "/", httpUri)
    httpsConfig = FDSClientConfiguration(region_name, False, False, True)
    httpsConfig.set_endpoint(endpoint)
    httpsUri = httpsConfig.get_base_uri()
    self.assertEqual("https://" + endpoint + "/", httpsUri)

  def test_uri(self):
    client = GalaxyFDSClient(access_key, access_secret,
        FDSClientConfiguration(region_name, False, False, False))
    bucket_name = self.bucket_name + "1"
    if (client.does_bucket_exist(bucket_name)):
      client.delete_bucket(bucket_name)
    client.create_bucket(bucket_name)
    client.delete_bucket(bucket_name)

  def test_normal_bucket(self):
    for bucket in self.client.list_buckets():
      print(bucket)
    bucket_name = self.bucket_name + "2"
    self.assertFalse(self.client.does_bucket_exist(bucket_name))
    self.client.create_bucket(bucket_name)
    self.assertTrue(self.client.does_bucket_exist(bucket_name))
    self.client.delete_bucket(bucket_name)
    self.assertFalse(self.client.does_bucket_exist(bucket_name))

  def test_create_and_delete_bucket(self):
    print(self.client.list_buckets())
    bucket_name = self.bucket_name + "3"
    try:
      self.client.create_bucket(bucket_name)
    except GalaxyFDSClientException as e:
      print(e.message)
    self.delete_objects_and_bucket(self.client, bucket_name)
    self.client.create_bucket(bucket_name)
    self.assertEquals(True, self.client.does_bucket_exist(bucket_name))
    self.client.delete_bucket(bucket_name)
    self.assertEquals(False, self.client.does_bucket_exist(bucket_name))
    try:
      self.client.delete_bucket(bucket_name)
    except GalaxyFDSClientException as e:
      print(e.message)

  def test_normal_object(self):
    object_name = "testPutGetObject_name"
    self.client.put_object(self.bucket_name, object_name, '')
    self.assertTrue(
      self.client.does_object_exists(self.bucket_name, object_name))
    print(self.client.list_objects(self.bucket_name))
    self.client.delete_object(self.bucket_name, object_name)
    self.assertFalse(
      self.client.does_object_exists(self.bucket_name, object_name))
    print(self.client.list_objects(self.bucket_name))

  def test_bucket_acl(self):
    print(self.bucket_name)

    self.client.get_bucket_acl(self.bucket_name)
    bucketAcl = AccessControlList()
    bucketAcl.add_grant(Grant(Grantee("111"), Permission.READ))
    bucketAcl.add_grant(Grant(Grantee('109901'), Permission.FULL_CONTROL))
    bucketAcl.add_grant(Grant(Grantee('123456'), Permission.SSO_WRITE))
    bucketAcl.add_grant(Grant(Grantee(appid), Permission.FULL_CONTROL))
    self.client.set_bucket_acl(self.bucket_name, bucketAcl)

    aclListGot = self.client.get_bucket_acl(self.bucket_name)
    readAclCnt = 0
    fullControlCnt = 0
    writeWithSSOCnt = 0
    for i in aclListGot.get_grant_list():
      if i['grantee']['id'] == '111':
        self.assertTrue(i['permission'].to_string() == Permission(Permission.READ).to_string())
        readAclCnt += 1
      elif i['grantee']['id'] == '109901':
        self.assertTrue(i['permission'].to_string() == Permission(Permission.FULL_CONTROL).to_string())
        fullControlCnt += 1
      elif i['grantee']['id'] == '123456':
        self.assertTrue(i['permission'].to_string() == Permission(Permission.SSO_WRITE).to_string())
        writeWithSSOCnt += 1
    self.assertTrue(readAclCnt == 1)
    self.assertTrue(fullControlCnt == 1)
    self.assertTrue(writeWithSSOCnt == 1)

#    self.client.set_bucket_acl(self.bucket_name, bucketAcl)
    acl = self.client.get_bucket_acl(self.bucket_name)
    self.assertTrue(bucketAcl.is_subset(acl))
    acl_client = GalaxyFDSClient(acl_ak, acl_access_secret,
        FDSClientConfiguration(region_name, False, False, False, endpoint=endpoint))
    object_name = "testBucketAcl7"
    acl_client.put_object(self.bucket_name, object_name, "hahhah")
    self.assertTrue(
      self.client.does_object_exists(self.bucket_name, object_name))
    acl_client.list_objects(self.bucket_name)
    acl_client.delete_object(self.bucket_name, object_name)
    self.assertFalse(
      self.client.does_object_exists(self.bucket_name, object_name))
    self.assertTrue(acl_client.does_bucket_exist(self.bucket_name))
    try:
      acl_client.delete_bucket(self.bucket_name)
    except GalaxyFDSClientException as e:
      print(e.message)
    self.assertTrue(self.client.does_bucket_exist(self.bucket_name))

  def test_object_acl(self):
    object_name = "test1"
    content = "test1"
    self.client.put_object(self.bucket_name, object_name, content)
    for bucket in self.client.list_objects(self.bucket_name):
      print(bucket)
    print(self.client.get_object_acl(self.bucket_name, object_name))
    objectAcl = AccessControlList()
    objectAcl.add_grant(Grant(Grantee("111"), Permission.READ))
    objectAcl.add_grant(Grant(Grantee("109901"), Permission.FULL_CONTROL))
    objectAcl.add_grant(Grant(Grantee(acl_ak), Permission.FULL_CONTROL))
    self.client.set_object_acl(self.bucket_name, object_name, objectAcl)
    acl = self.client.get_object_acl(self.bucket_name, object_name)
    self.assertTrue(objectAcl.is_subset(acl))

    acl_client = GalaxyFDSClient(acl_ak, acl_access_secret,
        FDSClientConfiguration(region_name, False, False, False, endpoint=endpoint))
    self.assertTrue(
        self.client.does_object_exists(self.bucket_name, object_name))
    print(acl_client.get_object(self.bucket_name, object_name))
    self.client.delete_object(self.bucket_name, object_name)
    self.assertFalse(
        self.client.does_object_exists(self.bucket_name, object_name))

  def test_get_object_and_metadata(self):
    object_name = "test1"
    content = "test1"
    self.client.put_object(self.bucket_name, object_name, content)
    whole_object = self.client.get_object(self.bucket_name, object_name)
    self.assertEqual(whole_object.get_next_chunk_as_string(), "test1")
    partial_object = self.client.get_object(self.bucket_name, object_name, 2)
    self.assertEqual(partial_object.get_next_chunk_as_string(), "st1")
    metadata = self.client.get_object_metadata(self.bucket_name, object_name)
    if IS_PY3:
      self.assertEqual(hashlib.md5("test1".encode("UTF-8")).hexdigest(), metadata.metadata["content-md5"])
    else:
      self.assertEqual(hashlib.md5("test1").hexdigest(), metadata.metadata["content-md5"])
    print(metadata.metadata)

  def test_rename_object(self):
    object_old_name = "test_old1"
    object_new_name = "test_new1"
    self.client.put_object(self.bucket_name, object_old_name, "")
    self.assertTrue(
      self.client.does_object_exists(self.bucket_name, object_old_name))
    self.assertFalse(
      self.client.does_object_exists(self.bucket_name, object_new_name))
    self.client.rename_object(self.bucket_name, object_old_name, object_new_name)
    self.assertFalse(
      self.client.does_object_exists(self.bucket_name, object_old_name))
    self.assertTrue(
      self.client.does_object_exists(self.bucket_name, object_new_name))
    self.client.delete_object(self.bucket_name, object_new_name)

  def test_generate_presigned_uri(self):
    object_name = "中文测试"
    content = "presigned"
    self.client.put_object(self.bucket_name, object_name, content)
    uri = self.client.generate_presigned_uri(None, self.bucket_name, object_name,
                                             time.time() * 1000 + 60000)
    download = urlopen(uri).read()
    if IS_PY3:
      download = download.decode(encoding="UTF-8")
    self.assertEqual(content, download)

  def test_invalid_object_metadata(self):
    metadata = FDSObjectMetadata()

    metadata.add_user_metadata(FDSObjectMetadata.USER_DEFINED_METADATA_PREFIX
                        + "test", "test-value")
    metadata.add_header(Common.CACHE_CONTROL, "no-cache")

    try:
      metadata.add_user_metadata("test-key", "test-vale")
      self.fail("Exception should not be thrown here")
    except:
      pass

  def test_abort_multipart_upload(self):
    object_name = "test_object"
    upload_token = self.client.init_multipart_upload(self.bucket_name, object_name);
    self.client.abort_multipart_upload(self.bucket_name, object_name, upload_token.upload_id)

  def test_list_multi_objects(self):
    test_content = ""
    obj_prefix = "obj_"
    # add 2000 objects to make sure the result is truncated
    for i in range(2000):
      self.client.put_object(self.bucket_name, obj_prefix+str(i), test_content)
    for obj in self.client.list_all_objects(self.bucket_name):
      self.client.delete_object(self.bucket_name, obj.object_name)

  def test_multipart_upload(self):
    object_name = "test_multipart_upload"
    part_num = 3
    part_content = "1"*5242880
    upload_list = []
    upload_token = self.client.init_multipart_upload(self.bucket_name, object_name)

    for i in range(part_num):
      upload_list.append(self.client.upload_part(self.bucket_name, object_name, upload_token.upload_id, i+1, part_content))

    upload_part_result = UploadPartResultList({"uploadPartResultList": upload_list})
    print(json.dumps(upload_part_result))
    self.client.complete_multipart_upload(bucket_name=self.bucket_name,
                                          object_name=object_name,
                                          upload_id=upload_token.upload_id,
                                          metadata=None,
                                          upload_part_result_list=json.dumps(upload_part_result))

    obj = self.client.get_object(self.bucket_name, object_name)
    length = 0
    for chunk in obj.stream:
      if IS_PY3:
        chunk = chunk.decode(encoding="UTF-8")
      length += len(chunk)
      for t in chunk:
        self.assertEqual(t, "1")

    obj.stream.close()
    print(length)
    self.assertEqual(length, part_num*5242880)