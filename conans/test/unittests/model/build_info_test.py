import os
import six
import unittest
from collections import defaultdict, namedtuple

from conans.client.generators import TXTGenerator
from conans.errors import ConanException
from conans.model.build_info import CppInfo, DepsCppInfo, Component
from conans.model.env_info import DepsEnvInfo, EnvInfo
from conans.model.user_info import DepsUserInfo
from conans.test.utils.test_files import temp_folder
from conans.util.files import mkdir


class BuildInfoTest(unittest.TestCase):

    def parse_test(self):
        text = """[includedirs]
C:/Whenever
[includedirs_Boost]
F:/ChildrenPath
[includedirs_My_Lib]
mylib_path
[includedirs_My_Other_Lib]
otherlib_path
[includedirs_My.Component.Lib]
my_component_lib
[includedirs_My-Component-Tool]
my-component-tool
        """
        deps_cpp_info, _, _ = TXTGenerator.loads(text)

        def assert_cpp(deps_cpp_info_test):
            self.assertEqual(deps_cpp_info_test.includedirs, ['C:/Whenever'])
            self.assertEqual(deps_cpp_info_test["Boost"].includedirs, ['F:/ChildrenPath'])
            self.assertEqual(deps_cpp_info_test["My_Lib"].includedirs, ['mylib_path'])
            self.assertEqual(deps_cpp_info_test["My_Other_Lib"].includedirs, ['otherlib_path'])
            self.assertEqual(deps_cpp_info_test["My-Component-Tool"].includedirs, ['my-component-tool'])

        assert_cpp(deps_cpp_info)
        # Now adding env_info
        text2 = text + """
[ENV_LIBA]
VAR2=23
"""
        deps_cpp_info, _, deps_env_info = TXTGenerator.loads(text2)
        assert_cpp(deps_cpp_info)
        self.assertEqual(deps_env_info["LIBA"].VAR2, "23")

        # Now only with user info
        text3 = text + """
[USER_LIBA]
VAR2=23
"""
        deps_cpp_info, deps_user_info, _ = TXTGenerator.loads(text3)
        assert_cpp(deps_cpp_info)
        self.assertEqual(deps_user_info["LIBA"].VAR2, "23")

        # Now with all
        text4 = text + """
[USER_LIBA]
VAR2=23

[ENV_LIBA]
VAR2=23
"""
        deps_cpp_info, deps_user_info, deps_env_info = TXTGenerator.loads(text4)
        assert_cpp(deps_cpp_info)
        self.assertEqual(deps_user_info["LIBA"].VAR2, "23")
        self.assertEqual(deps_env_info["LIBA"].VAR2, "23")

    def help_test(self):
        deps_env_info = DepsEnvInfo()
        deps_cpp_info = DepsCppInfo()
        deps_cpp_info.includedirs.append("C:/whatever")
        deps_cpp_info.includedirs.append("C:/whenever")
        deps_cpp_info.libdirs.append("C:/other")
        deps_cpp_info.libs.extend(["math", "winsock", "boost"])
        child = DepsCppInfo()
        child.includedirs.append("F:/ChildrenPath")
        child.cxxflags.append("cxxmyflag")
        deps_cpp_info._dependencies["Boost"] = child
        fakeconan = namedtuple("Conanfile", "deps_cpp_info cpp_info deps_env_info env_info user_info deps_user_info")
        output = TXTGenerator(fakeconan(deps_cpp_info, None, deps_env_info, None, {}, defaultdict(dict))).content
        deps_cpp_info2, _, _ = TXTGenerator.loads(output)
        self.assertEqual(deps_cpp_info.configs, deps_cpp_info2.configs)
        self.assertEqual(deps_cpp_info.includedirs, deps_cpp_info2.includedirs)
        self.assertEqual(deps_cpp_info.libdirs, deps_cpp_info2.libdirs)
        self.assertEqual(deps_cpp_info.bindirs, deps_cpp_info2.bindirs)
        self.assertEqual(deps_cpp_info.libs, deps_cpp_info2.libs)
        self.assertEqual(len(deps_cpp_info._dependencies),
                         len(deps_cpp_info2._dependencies))
        self.assertEqual(deps_cpp_info["Boost"].includedirs,
                         deps_cpp_info2["Boost"].includedirs)
        self.assertEqual(deps_cpp_info["Boost"].cxxflags,
                         deps_cpp_info2["Boost"].cxxflags)
        self.assertEqual(deps_cpp_info["Boost"].cxxflags, ["cxxmyflag"])

    def configs_test(self):
        deps_cpp_info = DepsCppInfo()
        deps_cpp_info.includedirs.append("C:/whatever")
        deps_cpp_info.debug.includedirs.append("C:/whenever")
        deps_cpp_info.libs.extend(["math"])
        deps_cpp_info.debug.libs.extend(["debug_Lib"])

        child = DepsCppInfo()
        child.includedirs.append("F:/ChildrenPath")
        child.debug.includedirs.append("F:/ChildrenDebugPath")
        child.cxxflags.append("cxxmyflag")
        child.debug.cxxflags.append("cxxmydebugflag")
        deps_cpp_info._dependencies["Boost"] = child

        deps_env_info = DepsEnvInfo()
        env_info_lib1 = EnvInfo()
        env_info_lib1.var = "32"
        env_info_lib1.othervar.append("somevalue")
        deps_env_info.update(env_info_lib1, "LIB1")

        deps_user_info = DepsUserInfo()
        deps_user_info["LIB2"].myuservar = "23"

        fakeconan = namedtuple("Conanfile", "deps_cpp_info cpp_info deps_env_info env_info user_info deps_user_info")
        output = TXTGenerator(fakeconan(deps_cpp_info, None, deps_env_info, deps_user_info, {}, defaultdict(dict))).content

        deps_cpp_info2, _, deps_env_info2 = TXTGenerator.loads(output)
        self.assertEqual(deps_cpp_info.includedirs, deps_cpp_info2.includedirs)
        self.assertEqual(deps_cpp_info.libdirs, deps_cpp_info2.libdirs)
        self.assertEqual(deps_cpp_info.bindirs, deps_cpp_info2.bindirs)
        self.assertEqual(deps_cpp_info.libs, deps_cpp_info2.libs)
        self.assertEqual(len(deps_cpp_info._dependencies),
                         len(deps_cpp_info2._dependencies))
        self.assertEqual(deps_cpp_info["Boost"].includedirs,
                         deps_cpp_info2["Boost"].includedirs)
        self.assertEqual(deps_cpp_info["Boost"].cxxflags,
                         deps_cpp_info2["Boost"].cxxflags)
        self.assertEqual(deps_cpp_info["Boost"].cxxflags, ["cxxmyflag"])

        self.assertEqual(deps_cpp_info.debug.includedirs, deps_cpp_info2.debug.includedirs)
        self.assertEqual(deps_cpp_info.debug.includedirs, ["C:/whenever"])

        self.assertEqual(deps_cpp_info.debug.libs, deps_cpp_info2.debug.libs)
        self.assertEqual(deps_cpp_info.debug.libs, ["debug_Lib"])

        self.assertEqual(deps_cpp_info["Boost"].debug.includedirs,
                         deps_cpp_info2["Boost"].debug.includedirs)
        self.assertEqual(deps_cpp_info["Boost"].debug.includedirs,
                         ["F:/ChildrenDebugPath"])
        self.assertEqual(deps_cpp_info["Boost"].debug.cxxflags,
                         deps_cpp_info2["Boost"].debug.cxxflags)
        self.assertEqual(deps_cpp_info["Boost"].debug.cxxflags, ["cxxmydebugflag"])

        self.assertEqual(deps_env_info["LIB1"].var, "32")
        self.assertEqual(deps_env_info["LIB1"].othervar, ["somevalue"])

        self.assertEqual(deps_user_info["LIB2"].myuservar, "23")

    def cpp_info_test(self):
        folder = temp_folder()
        mkdir(os.path.join(folder, "include"))
        mkdir(os.path.join(folder, "lib"))
        mkdir(os.path.join(folder, "local_bindir"))
        abs_folder = temp_folder()
        abs_include = os.path.join(abs_folder, "usr/include")
        abs_lib = os.path.join(abs_folder, "usr/lib")
        abs_bin = os.path.join(abs_folder, "usr/bin")
        mkdir(abs_include)
        mkdir(abs_lib)
        mkdir(abs_bin)
        info = CppInfo(folder)
        info.includedirs.append(abs_include)
        info.libdirs.append(abs_lib)
        info.bindirs.append(abs_bin)
        info.bindirs.append("local_bindir")
        print("result: ", info.include_paths, info.lib_paths, info.bin_paths)
        self.assertEqual(info.include_paths, [os.path.join(folder, "include"), abs_include])
        self.assertEqual(info.lib_paths, [os.path.join(folder, "lib"), abs_lib])
        self.assertEqual(info.bin_paths, [abs_bin,
                                          os.path.join(folder, "local_bindir")])

    def basic_components_test(self):
        cpp_info = CppInfo(None)
        component = cpp_info["my_component"]
        self.assertIn(component.name, "my_component")
        component.lib = "libhola"
        self.assertEqual(component.lib, "libhola")
        with six.assertRaisesRegex(self, ConanException, "'.lib' is already set for this Component"):
            component.exe = "hola.exe"
        component.lib = None
        component.exe = "hola.exe"
        self.assertEqual(component.lib, None)
        with six.assertRaisesRegex(self, ConanException, "'.exe' is already set for this Component"):
            component.lib = "libhola"

    def cpp_info_libs_components_fail_test(self):
        """
        Usage of .libs is not allowed in cpp_info when using Components
        """
        info = CppInfo(None)
        info.name = "Greetings"
        self.assertIn(info.name, "Greetings")
        info.libs = ["libgreet"]
        with six.assertRaisesRegex(self, ConanException, "Usage of Components with '.libs' or "
                                                         "'.exes' values is not allowed"):
            info["hola"].exe = "hola.exe"

        info.libs = []
        info["greet"].exe = "libgreet"
        with six.assertRaisesRegex(self, ConanException, "Setting first level libs is not supported "
                                                         "when Components are already in use"):
            info.libs = ["libgreet"]

    def cpp_info_libs_system_deps_order_test(self):
        info = CppInfo(None)
        info["LIB1"].lib = "lib1"
        info["LIB1"].system_deps = ["sys1", "sys11"]
        info["LIB1"].deps = ["LIB2"]
        info["LIB2"].lib = "lib2"
        info["LIB2"].system_deps = ["sys2"]
        info["LIB1"].deps = ["LIB3"]
        info["LIB3"].lib = "lib3"
        info["LIB3"].system_deps = ["sys3", "sys2"]
        self.assertEqual(['sys2', 'lib2', 'sys3', 'lib3', 'sys1', 'sys11', 'lib1'], info.libs)
        print(info.libs)

    def cppinfo_dirs_test(self):
        folder = temp_folder()
        info = CppInfo(folder)
        info.name = "OpenSSL"
        info["OpenSSL"].includedirs = ["include"]
        info["OpenSSL"].libdirs = ["lib"]
        info["OpenSSL"].builddirs = ["build"]
        info["OpenSSL"].bindirs = ["bin"]
        info["OpenSSL"].resdirs = ["res"]
        info["Crypto"].includedirs = ["headers"]
        info["Crypto"].libdirs = ["libraries"]
        info["Crypto"].builddirs = ["build_scripts"]
        info["Crypto"].bindirs = ["binaries"]
        info["Crypto"].resdirs = ["resources"]
        self.assertEqual(["include"], info["OpenSSL"].includedirs)
        self.assertEqual(["lib"], info["OpenSSL"].libdirs)
        self.assertEqual(["build"], info["OpenSSL"].builddirs)
        self.assertEqual(["bin"], info["OpenSSL"].bindirs)
        self.assertEqual(["res"], info["OpenSSL"].resdirs)
        self.assertEqual(["headers"], info["Crypto"].includedirs)
        self.assertEqual(["libraries"], info["Crypto"].libdirs)
        self.assertEqual(["build_scripts"], info["Crypto"].builddirs)
        self.assertEqual(["binaries"], info["Crypto"].bindirs)
        self.assertEqual(["resources"], info["Crypto"].resdirs)

        info["Crypto"].includedirs = ["different_include"]
        info["Crypto"].libdirs = ["different_lib"]
        info["Crypto"].builddirs = ["different_build"]
        info["Crypto"].bindirs = ["different_bin"]
        info["Crypto"].resdirs = ["different_res"]
        self.assertEqual(["different_include"], info["Crypto"].includedirs)
        self.assertEqual(["different_lib"], info["Crypto"].libdirs)
        self.assertEqual(["different_build"], info["Crypto"].builddirs)
        self.assertEqual(["different_bin"], info["Crypto"].bindirs)
        self.assertEqual(["different_res"], info["Crypto"].resdirs)

        info["Crypto"].includedirs.extend(["another_include"])
        info["Crypto"].includedirs.append("another_other_include")
        info["Crypto"].libdirs.extend(["another_lib"])
        info["Crypto"].libdirs.append("another_other_lib")
        info["Crypto"].builddirs.extend(["another_build"])
        info["Crypto"].builddirs.append("another_other_build")
        info["Crypto"].bindirs.extend(["another_bin"])
        info["Crypto"].bindirs.append("another_other_bin")
        info["Crypto"].resdirs.extend(["another_res"])
        info["Crypto"].resdirs.append("another_other_res")
        self.assertEqual(["different_include", "another_include", "another_other_include"],
                         info["Crypto"].includedirs)
        self.assertEqual(["different_lib", "another_lib", "another_other_lib"],
                         info["Crypto"].libdirs)
        self.assertEqual(["different_build", "another_build", "another_other_build"],
                         info["Crypto"].builddirs)
        self.assertEqual(["different_bin", "another_bin", "another_other_bin"],
                         info["Crypto"].bindirs)
        self.assertEqual(["different_res", "another_res", "another_other_res"],
                         info["Crypto"].resdirs)
