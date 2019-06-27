import unittest

from conans.client.generators.boostbuild import BoostBuildGenerator
from conans.model.build_info import CppInfo
from conans.model.conan_file import ConanFile
from conans.model.env_info import EnvValues
from conans.model.ref import ConanFileReference
from conans.model.settings import Settings
from conans.test.utils.tools import TestBufferConanOutput


class BoostJamGeneratorTest(unittest.TestCase):

    def variables_setup_test(self):

        conanfile = ConanFile(TestBufferConanOutput(), None)
        conanfile.initialize(Settings({}), EnvValues())

        ref = ConanFileReference.loads("MyPkg/0.1@lasote/stables")
        cpp_info = CppInfo("dummy_root_folder1")
        cpp_info._filter_empty = False  # For testing purposes
        cpp_info.defines = ["MYDEFINE1"]
        cpp_info.cflags.append("-Flag1=23")
        cpp_info._version = "1.3"
        cpp_info._description = "My cool description"
        cpp_info.libs = ["MyLib1"]
        conanfile.deps_cpp_info.update(cpp_info, ref.name)

        ref = ConanFileReference.loads("MyPkg2/0.1@lasote/stables")
        cpp_info = CppInfo("dummy_root_folder2")
        cpp_info._filter_empty = False  # For testing purposes
        cpp_info.libs = ["MyLib2"]
        cpp_info.defines = ["MYDEFINE2"]
        cpp_info._version = "2.3"
        cpp_info.exelinkflags = ["-exelinkflag"]
        cpp_info.sharedlinkflags = ["-sharedlinkflag"]
        cpp_info.cxxflags = ["-cxxflag"]
        cpp_info._public_deps = ["MyPkg"]
        cpp_info.libdirs.extend(["Path\\with\\slashes", "regular/path/to/dir"])
        cpp_info.includedirs.extend(["other\\Path\\with\\slashes", "other/regular/path/to/dir"])
        conanfile.deps_cpp_info.update(cpp_info, ref.name)

        generator = BoostBuildGenerator(conanfile)

        self.assertEqual("""lib MyLib1 :
	: # requirements
	<name>MyLib1
	<search>dummy_root_folder1/lib
	: # default-build
	: # usage-requirements
	<define>MYDEFINE1
	<include>dummy_root_folder1/include
	<cflags>-Flag1=23
	;

lib MyLib2 :
	: # requirements
	<name>MyLib2
	<search>dummy_root_folder2/lib
	<search>dummy_root_folder2/Path/with/slashes
	<search>dummy_root_folder2/regular/path/to/dir
	: # default-build
	: # usage-requirements
	<define>MYDEFINE2
	<include>dummy_root_folder2/include
	<include>dummy_root_folder2/other/Path/with/slashes
	<include>dummy_root_folder2/other/regular/path/to/dir
	<cxxflags>-cxxflag
	<ldflags>-sharedlinkflag
	;

alias conan-deps :
	MyLib1
	MyLib2
;
""", generator.content)
