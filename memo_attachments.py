"""Private Drive image attachments; existing memo sheet columns stay unchanged."""
import base64
import hashlib
import io
import json
import re
import uuid
from pathlib import Path
from PIL import Image
import streamlit as st
import streamlit.components.v1 as components
from shared_files import drive_client, upload, download, metadata, FOLDER

MARKER='\n\n[[MEMO_IMAGES_V1:'
clipboard=components.declare_component('memo_clipboard',path=str(Path(__file__).parent/'memo_clipboard'))


def split_content(content):
 body,sep,tail=content.rpartition(MARKER)
 if sep and tail.endswith(']]'):
  try:
   items=json.loads(tail[:-2])
   if isinstance(items,list) and len(items)<=5 and all(isinstance(x,dict) and re.fullmatch(r'[A-Za-z0-9_-]+',x.get('id','')) for x in items):return body,items
  except (ValueError,TypeError):pass
 return content,[]


def join_content(body,items):
 return body+(MARKER+json.dumps(items,ensure_ascii=False,separators=(',',':'))+']]' if items else '')


def decode_image(value):
 if not isinstance(value,str) or len(value)>7*1024*1024:raise ValueError('이미지는 장당 5MB 이하만 첨부할 수 있습니다.')
 try:
  header,payload=value.split(',',1)
  if not header.startswith('data:image/') or not header.endswith(';base64'):raise ValueError()
  data=base64.b64decode(payload,validate=True)
  if len(data)>5*1024*1024:raise ValueError()
  with Image.open(io.BytesIO(data)) as picture:
   if picture.width*picture.height>25000000:raise ValueError()
   fmt=picture.format
   picture.verify()
  types={'PNG':('png','image/png'),'JPEG':('jpg','image/jpeg'),'GIF':('gif','image/gif'),'WEBP':('webp','image/webp')}
  suffix,mime=types[fmt]
 except Exception:raise ValueError('PNG·JPG·GIF·WebP 이미지(장당 5MB, 2,500만 화소 이하)를 사용해 주세요.') from None
 return data,suffix,mime


def client_and_root():
 oauth=st.secrets.get('drive_oauth')
 info=st.secrets.get('gcp_service_account')
 if isinstance(info,str):info=json.loads(info)
 root=str(st.secrets.get('shared_drive_folder_id') or st.secrets.get('drive_folder_id','')).strip()
 if not root:raise ValueError('기존 Google Drive 저장 폴더 설정을 확인해 주세요.')
 client=drive_client(info,oauth=oauth)
 folder=metadata(client,root)
 if folder['mimeType']!=FOLDER or not folder.get('capabilities',{}).get('canAddChildren'):raise ValueError('Google Drive 저장 폴더에 파일 추가 권한이 필요합니다.')
 return client,root


def save_images(values,existing,token):
 if not isinstance(values,list) or len(values)+len(existing)>5:raise ValueError('메모당 이미지는 최대 5장까지 첨부할 수 있습니다.')
 decoded=[decode_image(v) for v in values]  # Validate every image before writing anything.
 if not decoded:return existing
 client,root=client_and_root()
 cache=st.session_state.setdefault('memo_image_uploads',{})
 result=list(existing)
 for data,suffix,mime in decoded:
  digest=hashlib.sha256((root+token).encode()+data).hexdigest()
  if digest not in cache:
   file=io.BytesIO(data);file.name='메모이미지_'+uuid.uuid4().hex+'.'+suffix;file.size=len(data);file.type=mime
   saved=upload(client,root,file)
   cache[digest]={'id':saved['id'],'name':saved['name']}
  result.append(cache[digest])
 return result


def show_images(items):
 if not items:return
 st.caption('첨부 이미지')
 for item in items:
  try:
   cache=st.session_state.setdefault('memo_image_previews',{})
   if item['id'] not in cache:
    client,_=client_and_root()
    meta=metadata(client,item['id'])
    if int(meta.get('size',0))>5*1024*1024:raise ValueError()
    data=download(client,meta)
    decode_image('data:image/png;base64,'+base64.b64encode(data).decode())
    if len(cache)>=20:cache.clear()
    cache[item['id']]=data
   st.image(cache[item['id']],caption=item.get('name','첨부 이미지'),width='stretch')
  except Exception:st.warning('첨부 이미지를 불러오지 못했습니다. Drive 연결과 파일 접근 권한을 확인해 주세요.')
