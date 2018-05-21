import unittest

from conans.test.utils.tools import TestClient
from conans.test.utils.test_files import temp_folder


class StorageConfTest(unittest.TestCase):

    def storage_short_paths_test(self):
        conanfile = """
from conans import ConanFile

class TestConan(ConanFile):
    name = "test"
    version = "1.0"
    short_paths = True
        """

        temp_dir = temp_folder()
        client = TestClient()
        client.run("config set 'storage.path=%s'" % temp_dir)
        client.save({"conanfile.py": conanfile})
        client.run("create . danimtb/testing")
        client.run("create . danimtb/testing")
