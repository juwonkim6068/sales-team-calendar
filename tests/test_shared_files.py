import io
import json
import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch
from googleapiclient.errors import HttpError
from httplib2 import Response

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import shared_files as files
from streamlit.testing.v1 import AppTest


class SharedFilesTests(unittest.TestCase):
    def test_explorer_search_type_and_sort(self):
        items = [
            {'id':'a','name':'견적.txt','mimeType':'text/plain','size':'100','modifiedTime':'2026-10-01'},
            {'id':'b','name':'계약.PDF','mimeType':'application/pdf','size':'200','modifiedTime':'2026-10-02'},
            {'id':'c','name':'자료','mimeType':files.FOLDER},
        ]
        self.assertEqual([x['id'] for x in files.filter_items(items, order='크기순')], ['c','b','a'])
        self.assertEqual([x['id'] for x in files.filter_items(items, category='파일', order='최신순')], ['b','a'])
        self.assertEqual([x['id'] for x in files.filter_items(items, 'pdf')], ['b'])
        self.assertEqual([x['id'] for x in files.filter_items(items, category='폴더')], ['c'])
        self.assertEqual(files.filter_items(items, '없음'), [])
        self.assertEqual(files.format_size('512'), '512 B')
        self.assertEqual(files.format_size('2048'), '2.0 KB')
        self.assertEqual(files.format_size(None), '—')

    def test_explorer_select_download_and_breadcrumb(self):
        root = {'id':'root','name':'자료실','mimeType':files.FOLDER,'driveId':'drive','capabilities':{'canAddChildren':True}}
        child = {'id':'child','name':'하위폴더','mimeType':files.FOLDER,'parents':['root']}
        document = {'id':'doc','name':'보고서.txt','mimeType':'text/plain','size':'10'}
        with patch.object(files, 'drive_client'), patch.object(files, 'metadata', side_effect=lambda c,i:root if i=='root' else child), patch.object(files, 'children', side_effect=lambda c,i:[child,document] if i=='root' else []), patch.object(files, 'download', return_value=b'offline') as download:
            at = AppTest.from_string('from shared_files import render_shared_files\nrender_shared_files({})')
            at.secrets['shared_drive_folder_id']='root'
            at.run()
            self.assertFalse(at.exception)
            download.assert_not_called()
            next(b for b in at.button if b.label=='📄 보고서.txt').click().run()
            next(b for b in at.button if b.label=='↓ 다운로드 준비').click().run()
            self.assertFalse(at.exception)
            download.assert_called_once()
            self.assertEqual(at.session_state['shared_file_download'], ('doc',b'offline'))
            next(b for b in at.button if b.label=='📁 하위폴더').click().run()
            self.assertFalse(at.exception)
            next(b for b in at.button if b.label=='🏠 공유파일').click().run()
            self.assertFalse(at.exception)
            self.assertEqual(at.session_state['shared_file_path'][-1]['id'],'root')
            at.text_input(key='shared_file_search_root').set_value('없는 파일').run()
            self.assertTrue(any('검색 결과가 없습니다' in x.value for x in at.info))

    def test_oauth_client_uses_user_credentials_without_service_account(self):
        oauth = {'client_id': 'test-client', 'client_secret': 'test-secret', 'refresh_token': 'test-refresh'}
        with patch.object(files, 'UserCredentials') as user, patch.object(files.Credentials, 'from_service_account_info') as service, patch.object(files, 'build') as build:
            files.drive_client(None, oauth=oauth)
            self.assertEqual(user.call_args.kwargs['token_uri'], 'https://oauth2.googleapis.com/token')
            self.assertEqual(user.call_args.kwargs['refresh_token'], 'test-refresh')
            self.assertEqual(build.call_args.kwargs['credentials'], user.return_value)
            service.assert_not_called()

    def test_incomplete_oauth_never_falls_back_to_service_account(self):
        with patch.object(files.Credentials, 'from_service_account_info') as service:
            for oauth in ({}, {'client_id': 'test'}):
                with self.assertRaises(ValueError):
                    files.drive_client({}, oauth=oauth)
            service.assert_not_called()

    def test_personal_drive_with_oauth_is_supported(self):
        root = {'id': 'personal', 'name': '내 폴더', 'mimeType': files.FOLDER, 'capabilities': {'canAddChildren': True}}
        with patch.object(files, 'drive_client') as client, patch.object(files, 'metadata', return_value=root), patch.object(files, 'children', return_value=[]):
            at = AppTest.from_string('from shared_files import render_shared_files\nrender_shared_files(None)')
            at.secrets['shared_drive_folder_id'] = 'personal'
            at.secrets['drive_oauth'] = {'client_id': 'test', 'client_secret': 'test', 'refresh_token': 'test'}
            at.run()
            self.assertFalse(at.exception)
            self.assertFalse(at.error)
            self.assertTrue(any('Google 사용자 OAuth' in c.value for c in at.caption))
            self.assertIsNotNone(client.call_args.kwargs['oauth'])

    def test_expired_oauth_is_reported_without_secret_details(self):
        with patch.object(files, 'drive_client', side_effect=files.RefreshError('DO_NOT_EXPOSE')):
            at = AppTest.from_string('from shared_files import render_shared_files\nrender_shared_files(None)')
            at.secrets['shared_drive_folder_id'] = 'root'
            at.secrets['drive_oauth'] = {'client_id': 'test'}
            at.run()
            self.assertFalse(at.exception)
            self.assertIn('인증을 갱신하지 못했습니다', at.error[0].value)
            self.assertNotIn('DO_NOT_EXPOSE', at.error[0].value)

    def test_safe_drive_errors(self):
        cases = [(404, 'notFound', '404'), (403, 'accessNotConfigured', 'API가 비활성화'), (403, 'storageQuotaExceeded', '저장공간 제한'), (403, 'forbidden', '접근이 거부'), (401, 'authError', '인증이 거부')]
        for status, reason, expected in cases:
            with self.subTest(status=status, reason=reason):
                body = json.dumps({'error': {'message': 'DO_NOT_EXPOSE', 'errors': [{'reason': reason}]}}).encode()
                error = HttpError(Response({'status': str(status)}), body)
                message = files.drive_error_message(error)
                self.assertIn(expected, message)
                self.assertNotIn('DO_NOT_EXPOSE', message)

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
            next(b for b in at.button if b.label == '📄 보고서.txt').click().run()
            self.assertFalse(at.exception)
            next(b for b in at.button if b.label == '이동').click().run()
            self.assertFalse(at.exception)
            self.assertEqual(client.files.return_value.update.call_args.kwargs['addParents'], 'child')
            self.assertEqual(client.files.return_value.update.call_args.kwargs['removeParents'], 'root')
            self.assertNotIn('shared_file_selected',at.session_state)
            # AppTest 1.50 retains the removed move selectbox after st.rerun.
            # Re-render the resulting folder in a fresh runner, then navigate.
            current_path=at.session_state['shared_file_path']
            at=AppTest.from_string('from shared_files import render_shared_files\nrender_shared_files({})')
            at.secrets['shared_drive_folder_id']='root'
            at.session_state['shared_file_path']=current_path
            at.run()
            next(b for b in at.button if b.label == '📁 견적').click().run()
            self.assertFalse(at.exception)
            self.assertEqual(at.session_state['shared_file_path'][-1]['id'], 'child')
            self.assertTrue(any(b.label == '↑ 상위' for b in at.button))

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
