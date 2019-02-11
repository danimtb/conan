import os
import time
import traceback

from conans.client.remote_manager import check_compressed_files
from conans.client.rest.client_routes import ClientV2Router
from conans.client.rest.rest_client_common import RestCommonMethods, get_exception_from_error
from conans.client.rest.uploader_downloader import Downloader, Uploader
from conans.errors import ConanException, NotFoundException
from conans.model.info import ConanInfo
from conans.model.manifest import FileTreeManifest
from conans.model.ref import PackageReference, ConanFileReference
from conans.paths import EXPORT_SOURCES_TGZ_NAME, EXPORT_TGZ_NAME, \
    PACKAGE_TGZ_NAME
from conans.util.dates import iso8601_to_str
from conans.util.files import decode_text
from conans.util.log import logger


class RestV2Methods(RestCommonMethods):

    def __init__(self, remote_url, token, custom_headers, output, requester, verify_ssl,
                 put_headers=None, checksum_deploy=False):

        super(RestV2Methods, self).__init__(remote_url, token, custom_headers, output, requester,
                                            verify_ssl, put_headers)
        self._checksum_deploy = checksum_deploy

    @property
    def router(self):
        return ClientV2Router(self.remote_url.rstrip("/"))

    def _get_file_list_json(self, url):
        data = self.get_json(url)
        # Discarding (.keys()) still empty metadata for files
        data["files"] = list(data["files"].keys())
        return data

    def _get_remote_file_contents(self, url):
        downloader = Downloader(self.requester, self._output, self.verify_ssl)
        contents = downloader.download(url, auth=self.auth)
        return contents

    def _get_snapshot(self, url):
        try:
            data = self._get_file_list_json(url)
            files_list = [os.path.normpath(filename) for filename in data["files"]]
        except NotFoundException:
            files_list = []
        return files_list

    def get_conan_manifest(self, ref):
        url = self.router.recipe_manifest(ref)
        content = self._get_remote_file_contents(url)
        return FileTreeManifest.loads(decode_text(content))

    def get_package_manifest(self, pref):
        url = self.router.package_manifest(pref)
        content = self._get_remote_file_contents(url)
        try:
            return FileTreeManifest.loads(decode_text(content))
        except Exception as e:
            msg = "Error retrieving manifest file for package " \
                  "'{}' from remote ({}): '{}'".format(pref.full_repr(), self.remote_url, e)
            logger.error(msg)
            logger.error(traceback.format_exc())
            raise ConanException(msg)

    def get_package_info(self, package_reference):
        url = self.router.package_info(package_reference)
        content = self._get_remote_file_contents(url)
        return ConanInfo.loads(decode_text(content))

    def get_recipe(self, ref, dest_folder):
        url = self.router.recipe_snapshot(ref)
        data = self._get_file_list_json(url)
        files = data["files"]
        check_compressed_files(EXPORT_TGZ_NAME, files)
        if EXPORT_SOURCES_TGZ_NAME in files:
            files.remove(EXPORT_SOURCES_TGZ_NAME)

        # If we didn't indicated reference, server got the latest, use absolute now, it's safer
        urls = {fn: self.router.recipe_file(ref, fn) for fn in files}
        self._download_and_save_files(urls, dest_folder, files)
        ret = {fn: os.path.join(dest_folder, fn) for fn in files}
        return ret

    def get_recipe_sources(self, ref, dest_folder):
        url = self.router.recipe_snapshot(ref)
        data = self._get_file_list_json(url)
        files = data["files"]
        check_compressed_files(EXPORT_SOURCES_TGZ_NAME, files)
        if EXPORT_SOURCES_TGZ_NAME not in files:
            return None
        files = [EXPORT_SOURCES_TGZ_NAME, ]

        # If we didn't indicated reference, server got the latest, use absolute now, it's safer
        new_ref = ConanFileReference.loads(data["reference"])
        urls = {fn: self.router.recipe_file(new_ref, fn) for fn in files}
        self._download_and_save_files(urls, dest_folder, files)
        ret = {fn: os.path.join(dest_folder, fn) for fn in files}
        return ret

    def get_package(self, pref, dest_folder):
        url = self.router.package_snapshot(pref)
        data = self._get_file_list_json(url)
        files = data["files"]
        check_compressed_files(PACKAGE_TGZ_NAME, files)
        # If we didn't indicated reference, server got the latest, use absolute now, it's safer
        pref = PackageReference.loads(data["reference"])
        urls = {fn: self.router.package_file(pref, fn) for fn in files}
        self._download_and_save_files(urls, dest_folder, files)
        ret = {fn: os.path.join(dest_folder, fn) for fn in files}
        return ret

    def get_path(self, ref, package_id, path):

        if not package_id:
            url = self.router.recipe_snapshot(ref)
        else:
            pref = PackageReference(ref, package_id)
            url = self.router.package_snapshot(pref)

        try:
            files = self._get_file_list_json(url)
        except NotFoundException:
            if package_id:
                raise NotFoundException("Package %s:%s not found" % (ref, package_id))
            else:
                raise NotFoundException("Recipe %s not found" % str(ref))

        def is_dir(the_path):
            if the_path == ".":
                return True
            for the_file in files["files"]:
                if the_path == the_file:
                    return False
                elif the_file.startswith(the_path):
                    return True
            raise NotFoundException("The specified path doesn't exist")

        if is_dir(path):
            ret = []
            for the_file in files["files"]:
                if path == "." or the_file.startswith(path):
                    tmp = the_file[len(path)-1:].split("/", 1)[0]
                    if tmp not in ret:
                        ret.append(tmp)
            return sorted(ret)
        else:
            if not package_id:
                url = self.router.recipe_file(ref, path)
            else:
                pref = PackageReference(ref, package_id)
                url = self.router.package_file(pref, path)

            content = self._get_remote_file_contents(url)
            return decode_text(content)

    def _upload_recipe(self, ref, files_to_upload, retry, retry_wait):
        # Direct upload the recipe
        urls = {fn: self.router.recipe_file(ref, fn) for fn in files_to_upload}
        self._upload_files(files_to_upload, urls, retry, retry_wait)

    def _upload_package(self, pref, files_to_upload, retry, retry_wait):
        urls = {fn: self.router.package_file(pref, fn)
                for fn in files_to_upload}
        self._upload_files(files_to_upload, urls, retry, retry_wait)

    def _upload_files(self, files, urls, retry, retry_wait):
        t1 = time.time()
        failed = []
        uploader = Uploader(self.requester, self._output, self.verify_ssl)
        # Take advantage of filenames ordering, so that conan_package.tgz and conan_export.tgz
        # can be < conanfile, conaninfo, and sent always the last, so smaller files go first
        for filename in sorted(files, reverse=True):
            self._output.rewrite_line("Uploading %s" % filename)
            resource_url = urls[filename]
            try:
                response = uploader.upload(resource_url, files[filename], auth=self.auth,
                                           dedup=self._checksum_deploy, retry=retry,
                                           retry_wait=retry_wait,
                                           headers=self._put_headers)
                self._output.writeln("")
                if not response.ok:
                    self._output.error("\nError uploading file: %s, '%s'" % (filename,
                                                                             response.content))
                    failed.append(filename)
                else:
                    pass
            except Exception as exc:
                self._output.error("\nError uploading file: %s, '%s'" % (filename, exc))
                failed.append(filename)

        if failed:
            raise ConanException("Execute upload again to retry upload the failed files: %s"
                                 % ", ".join(failed))
        else:
            logger.debug("\nUPLOAD: All uploaded! Total time: %s\n" % str(time.time() - t1))

    def _download_and_save_files(self, urls, dest_folder, files):
        downloader = Downloader(self.requester, self._output, self.verify_ssl)
        # Take advantage of filenames ordering, so that conan_package.tgz and conan_export.tgz
        # can be < conanfile, conaninfo, and sent always the last, so smaller files go first
        for filename in sorted(files, reverse=True):
            if self._output:
                self._output.writeln("Downloading %s" % filename)
            resource_url = urls[filename]
            abs_path = os.path.join(dest_folder, filename)
            downloader.download(resource_url, abs_path, auth=self.auth)

    def _remove_conanfile_files(self, ref, files):
        # V2 === revisions, do not remove files, it will create a new revision if the files changed
        return

    def remove_packages(self, ref, package_ids=None):
        """ Remove any packages specified by package_ids"""
        self.check_credentials()
        if not package_ids:
            url = self.router.remove_all_packages(ref)
            response = self.requester.delete(url, auth=self.auth, headers=self.custom_headers,
                                             verify=self.verify_ssl)
            if response.status_code != 200:  # Error message is text
                response.charset = "utf-8"  # To be able to access ret.text (ret.content are bytes)
                raise get_exception_from_error(response.status_code)(response.text)
        for pid in package_ids:
            pref = PackageReference(ref, pid)
            url = self.router.remove_package(pref)
            response = self.requester.delete(url, auth=self.auth, headers=self.custom_headers,
                                             verify=self.verify_ssl)
            if response.status_code == 404:
                raise NotFoundException("Package not found: {}".format(pref.full_repr()))
            if response.status_code != 200:  # Error message is text
                response.charset = "utf-8"  # To be able to access ret.text (ret.content are bytes)
                raise get_exception_from_error(response.status_code)(response.text)

    def get_recipe_revisions(self, ref):
        url = self.router.recipe_revisions(ref)
        data = self.get_json(url)
        return {"revisions": [iso8601_to_str(r) for r in data["revisions"]]}

    def get_package_revisions(self, pref):
        url = self.router.package_revisions(pref)
        data = self.get_json(url)
        return {"revisions": [iso8601_to_str(r) for r in data["revisions"]]}

    def get_latest_recipe_revision(self, ref):
        url = self.router.recipe_latest(ref)
        data = self.get_json(url)
        rev = data["revision"]
        # Ignored data["time"]
        return ref.copy_with_rev(rev)

    def get_latest_package_revision(self, pref):
        url = self.router.package_latest(pref)
        data = self.get_json(url)
        prev = data["revision"]
        # Ignored data["time"]
        return pref.copy_with_rev(prev)
