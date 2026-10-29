import base64
import io
import unittest
from unittest.mock import patch, MagicMock
from PIL import Image
from memo_attachments import decode_image,split_content,join_content,save_images

def image():
 out=io.BytesIO();Image.new('RGB',(3,3)).save(out,format='PNG')
 return 'data:image/png;base64,'+base64.b64encode(out.getvalue()).decode()

class MemoAttachmentTests(unittest.TestCase):
 def test_legacy_and_attachment_round_trip(self):
  self.assertEqual(split_content('기존 메모'),('기존 메모',[]))
  items=[{'id':'test_image_123','name':'이미지.png'}]
  self.assertEqual(split_content(join_content('본문',items)),('본문',items))
 def test_rejects_invalid_images(self):
  for value in ['data:image/png;base64,SGVsbG8=','https://example.test/pic.png','data:image/svg+xml;base64,PHN2Zz4=']:
   with self.assertRaises(ValueError):decode_image(value)
  self.assertEqual(decode_image(image())[1:],('png','image/png'))
 def test_retry_reuses_uploaded_file_and_validates_before_upload(self):
  with patch('memo_attachments.st.session_state',{}),patch('memo_attachments.client_and_root',return_value=(MagicMock(),'root')),patch('memo_attachments.upload',return_value={'id':'saved_123','name':'image.png'}) as upload:
   first=save_images([image()],[],'memo1')
   self.assertEqual(save_images([image()],[],'memo1'),first)
   upload.assert_called_once()
   with self.assertRaises(ValueError):save_images([image(),'invalid'],[],'memo2')
   upload.assert_called_once()
 def test_attachment_limit(self):
  with self.assertRaises(ValueError):save_images([image()],[{'id':'a'}]*5,'memo1')
