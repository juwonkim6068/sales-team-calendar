import unittest
from unittest.mock import patch
from customer_workspace import drive_file_id, load_drive_workbook
from customer_excel import workbook_bytes

class CustomerDriveTests(unittest.TestCase):
 def test_link_formats_and_host_validation(self):
  key='example_file_12345'
  for value in (key,f'https://drive.google.com/file/d/{key}/view',f'https://drive.google.com/open?id={key}'):
   self.assertEqual(drive_file_id(value),key)
  for value in ('https://evil.test/file/d/example_file_12345','https://drive.google.com/drive/folders/example_file_12345','http://drive.google.com/open?id=example_file_12345'):
   with self.assertRaises(ValueError):drive_file_id(value)

 @patch('customer_workspace.st.secrets',{})
 @patch('shared_files.download')
 @patch('shared_files.metadata')
 @patch('shared_files.drive_client')
 def test_fetch_validates_workbook_and_size(self,client,metadata,download):
  metadata.return_value={'id':'example_file_12345','name':'거래처.xlsx','size':100}
  download.return_value=workbook_bytes()
  name,payload=load_drive_workbook('example_file_12345',{})
  self.assertEqual(name,'거래처.xlsx')
  self.assertTrue(payload)
  metadata.return_value['size']=11*1024*1024
  download.reset_mock()
  with self.assertRaises(ValueError):load_drive_workbook('example_file_12345',{})
  download.assert_not_called()
