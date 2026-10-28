import io
import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import shared_files as files
from streamlit.testing.v1 import AppTest


class SharedFilesTests(unittest.TestCase):
    def test_paginated_folder_listing(self):
        client = MagicMock()
        client.files.return_value.list.return_value.execute.side_effect = [
            {'files': [{'id': 'a'}], 'nextPageToken': 'next'}, {'files': [{'id': 'b'}]}]
        self.assertEqual(files.children(client, 'root'), [{'id': 'a'}, {'id': 'b'}])
        calls = client.files.return_value.list.call_args_list
        self.assertEqual(calls[1].kwargs['pageToken'], 'next')
        self.assertEqual(calls[0].kwargs['q'], "'root' in parents and trashed = false")
        self.assertTrue(calls[0].kwargs['includeItemsFromAllDrives'])

    def test_upload_target_and_size_limit(self):
        client = MagicMock()
        uploaded = io.BytesIO(b'hello')
        uploaded.name, uploaded.type, uploaded.size = 'report.txt', 'text/plain', 5
        files.upload(client, 'child', uploaded)
        options = client.files.return_value.create.call_args.kwargs
        self.assertEqual(options['body'], {'name': 'report.txt', 'parents': ['child']})
        self.assertEqual(options['media_body'].getbytes(0, 5), b'hello')
        client.reset_mock()
        uploaded.size = files.MAX_BYTES + 1
        with self.assertRaises(ValueError):
            files.upload(client, 'child', uploaded)
        client.files.assert_not_called()

    def test_download_bytes_and_limit(self):
        client = MagicMock()
        with patch.object(files, 'MediaIoBaseDownload') as reader:
            def make_reader(buffer, request):
                buffer.write(b'downloaded')
                result = MagicMock()
                result.next_chunk.return_value = (None, True)
                return result
            reader.side_effect = make_reader
            self.assertEqual(files.download(client, {'id': 'file', 'size': '10'}), b'downloaded')
            self.assertEqual(client.files.return_value.get_media.call_args.kwargs['fileId'], 'file')
        client.reset_mock()
        with self.assertRaises(ValueError):
            files.download(client, {'id': 'huge', 'size': str(files.MAX_BYTES + 1)})
        client.files.assert_not_called()

    def test_folder_names(self):
        self.assertEqual(files.clean_name('  영업자료  '), '영업자료')
        for invalid in ('', ' ', '.', '..', 'a/b', 'a\\b', 'a\x00'):
            with self.subTest(name=invalid), self.assertRaises(ValueError):
                files.clean_name(invalid)

    def test_missing_configuration_ui(self):
        at = AppTest.from_string('from shared_files import render_shared_files\nrender_shared_files(None)')
        at.secrets['offline_test'] = True
        at.run()
        self.assertFalse(at.exception)
        self.assertIn('shared_drive_folder_id', at.info[0].value)

    def test_folder_navigation_create_and_move_ui(self):
        root = {'id': 'root', 'name': '공유', 'mimeType': files.FOLDER, 'driveId': 'drive', 'capabilities': {'canAddChildren': True}}
        child = {'id': 'child', 'name': '견적', 'mimeType': files.FOLDER, 'parents': ['root']}
        document = {'id': 'doc', 'name': '보고서.txt', 'mimeType': 'text/plain', 'size': '10'}
        client = MagicMock()
        with patch.object(files, 'drive_client', return_value=client), patch.object(files, 'metadata', side_effect=lambda c, i: root if i == 'root' else child), patch.object(files, 'children', side_effect=lambda c, i: [child, document] if i == 'root' else []):
            at = AppTest.from_string('from shared_files import render_shared_files\nrender_shared_files({})')
            at.secrets['shared_drive_folder_id'] = 'root'
            at.run()
            self.assertFalse(at.exception)
            at.text_input[0].set_value('계약')
            next(b for b in at.button if b.label == '폴더 생성').click().run()
            self.assertFalse(at.exception)
            self.assertEqual(client.files.return_value.create.call_args.kwargs['body'], {'name': '계약', 'mimeType': files.FOLDER, 'parents': ['root']})
            next(b for b in at.button if b.label == '이동').click().run()
            self.assertFalse(at.exception)
            self.assertEqual(client.files.return_value.update.call_args.kwargs['addParents'], 'child')
            self.assertEqual(client.files.return_value.update.call_args.kwargs['removeParents'], 'root')
            next(b for b in at.button if b.label == '📁 견적').click().run()
            self.assertFalse(at.exception)
            self.assertEqual(at.session_state['shared_file_path'][-1]['id'], 'child')
            self.assertTrue(any(b.label == '⬆️ 상위 폴더' for b in at.button))

    def test_personal_drive_is_rejected(self):
        root = {'id': 'root', 'name': '개인 폴더', 'mimeType': files.FOLDER}
        with patch.object(files, 'drive_client'), patch.object(files, 'metadata', return_value=root), patch.object(files, 'children') as listing:
            at = AppTest.from_string('from shared_files import render_shared_files\nrender_shared_files({})')
            at.secrets['shared_drive_folder_id'] = 'root'
            at.run()
            self.assertFalse(at.exception)
            self.assertTrue(at.error)
            listing.assert_not_called()


if __name__ == '__main__':
    unittest.main()
