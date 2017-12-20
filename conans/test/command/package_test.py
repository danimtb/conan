import unittest

from conans import tools
from conans.test.utils.tools import TestClient
import os
from conans.paths import CONANFILE
from conans.util.files import load
from conans.test.utils.test_files import temp_folder
from nose_parameterized import parameterized


class PackageLocalCommandTest(unittest.TestCase):

    def package_with_destination_test(self):
        client = TestClient()

        def prepare_for_package(the_client):
            the_client.save({"src/header.h": "contents"}, clean_first=True)
            the_client.run("new lib/1.0 -s")

            # don't need real build
            tools.replace_in_file(os.path.join(client.current_folder,
                                               "conanfile.py"), "cmake =",
                                  "return\n#")
            the_client.run("install . --install-folder build")
            the_client.run("build . --build-folder build2 --install-folder build")

        # In current dir subdir
        prepare_for_package(client)
        client.run("package . --build-folder build2 --install-folder build --package_folder=subdir")
        self.assertTrue(os.path.exists(os.path.join(client.current_folder, "subdir")))

        # In current dir subdir with conanfile path
        prepare_for_package(client)
        client.run("package ./conanfile.py --build-folder build2 --install-folder build --package_folder=subdir")
        self.assertTrue(os.path.exists(os.path.join(client.current_folder, "subdir")))

        # Default path
        prepare_for_package(client)
        client.run("package . --build-folder build")
        self.assertTrue(os.path.exists(os.path.join(client.current_folder, "build", "package")))

        # Default path with conanfile path
        prepare_for_package(client)
        client.run("package conanfile.py --build-folder build")
        self.assertTrue(os.path.exists(os.path.join(client.current_folder, "build", "package")))

        # Abs path
        prepare_for_package(client)
        pf = os.path.join(client.current_folder, "mypackage/two")
        client.run("package . --build-folder build --package_folder='%s'" % pf)
        self.assertTrue(os.path.exists(os.path.join(client.current_folder, "mypackage", "two")))

        # Abs path with conanfile path
        prepare_for_package(client)
        pf = os.path.join(client.current_folder, "mypackage/two")
        os.rename(os.path.join(client.current_folder, "conanfile.py"),
                  os.path.join(client.current_folder, "my_conanfile.py"))
        client.run("package ./my_conanfile.py --build-folder build --package_folder='%s'" % pf)
        self.assertTrue(os.path.exists(os.path.join(client.current_folder, "mypackage", "two")))

    def package_with_reference_errors_test(self):
        client = TestClient()
        error = client.run("package MyLib/0.1@lasote/stable", ignore_error=True)
        self.assertTrue(error)
        self.assertIn("conan package' doesn't accept a reference anymore",
                      client.out)

    def local_package_test(self):
        client = TestClient()
        conanfile_template = """
from conans import ConanFile

class MyConan(ConanFile):
    def package(self):
        self.copy(pattern="*.h", dst="include", src="include")
"""
        client.save({"include/file.h": "foo",
                     CONANFILE: conanfile_template})
        client.run("install")
        path = client.current_folder
        client.run('package "%s"' % path)
        package_folder = os.path.join(client.current_folder, "package")
        content = load(os.path.join(package_folder, "include/file.h"))
        self.assertEqual(content, "foo")
        self.assertEqual(sorted(os.listdir(package_folder)),
                         sorted(["include", "conaninfo.txt", "conanmanifest.txt"]))
        self.assertEqual(os.listdir(os.path.join(package_folder, "include")), ["file.h"])

    @parameterized.expand([(False, False), (True, False), (True, True), (False, True)])
    def local_package_build_test(self, default_folder, conanfile_path):
        client = TestClient()
        conanfile_template = """
from conans import ConanFile

class MyConan(ConanFile):
    def package(self):
        self.copy(pattern="*.h", dst="include", src="include")
        self.copy(pattern="*.lib")
"""

        client.save({"include/file.h": "foo",
                     "build/lib/mypkg.lib": "mylib",
                     CONANFILE: conanfile_template})
        path = client.current_folder
        client.current_folder = os.path.join(client.current_folder, "build")
        client.run("install ..")

        if default_folder:
            package_folder = os.path.join(client.current_folder, "package")
            path = "../conanfile.py" if conanfile_path else ".."
            client.run('package {0} --build-folder=.'.format(path))
            self.assertEqual(sorted(os.listdir(package_folder)),
                             sorted(["include", "lib", "conaninfo.txt", "conanmanifest.txt"]))
        else:
            package_folder = temp_folder()
            client.current_folder = package_folder
            build_folder = os.path.join(path, "build")

            if conanfile_path:
                path = os.path.join(path, "conanfile.py")

            client.run('package "{0}" --build_folder="{2}"'
                       ' --package_folder="{1}"'.format(path, package_folder, build_folder))
            self.assertEqual(sorted(os.listdir(package_folder)),
                             sorted(["include", "lib", "conaninfo.txt",
                                     "conanmanifest.txt"]))

        content = load(os.path.join(package_folder, "include/file.h"))
        self.assertEqual(content, "foo")
        self.assertEqual(os.listdir(os.path.join(package_folder, "include")), ["file.h"])
        self.assertEqual(os.listdir(os.path.join(package_folder, "lib")), ["mypkg.lib"])

    @parameterized.expand([(False, False), (True, False), (True, True), (False, True)])
    def local_package_source_test(self, default_folder, conanfile_path):
        client = TestClient()
        conanfile_template = """
from conans import ConanFile

class MyConan(ConanFile):
    def package(self):
        self.copy(pattern="*.h", dst="include", src="include")
        self.copy(pattern="*.lib")
"""

        client.save({"src/include/file.h": "foo",
                     "build/lib/mypkg.lib": "mylib",
                     CONANFILE: conanfile_template})
        conanfile_folder = client.current_folder
        path = conanfile_folder
        client.current_folder = os.path.join(client.current_folder, "build")
        client.run("install ..")

        if default_folder:
            package_folder = os.path.join(client.current_folder, "package")
            path = "../conanfile.py" if conanfile_path else ".."
            client.run('package {0} --build_folder=. --source_folder=../src'.format(path))
        else:
            package_folder = temp_folder()

            if conanfile_path:
                path = os.path.join(path, "conanfile.py")

            client.run('package "{0}" --build_folder="{1}/build" '
                       '--package_folder="{2}" --source_folder="{1}/src"'.
                       format(path, conanfile_folder, package_folder))
        content = load(os.path.join(package_folder, "include/file.h"))
        self.assertEqual(content, "foo")
        self.assertEqual(sorted(os.listdir(package_folder)),
                         sorted(["include", "lib", "conaninfo.txt", "conanmanifest.txt"]))
        self.assertEqual(os.listdir(os.path.join(package_folder, "include")), ["file.h"])
        self.assertEqual(os.listdir(os.path.join(package_folder, "lib")), ["mypkg.lib"])
