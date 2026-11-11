import ast
from datetime import date
from pathlib import Path
import unittest
from unittest.mock import MagicMock, patch

import streamlit as st
from streamlit.testing.v1 import AppTest

APP = Path(__file__).resolve().parents[1] / 'app.py'
HEAD = next(ast.literal_eval(n.value) for n in ast.parse(APP.read_text()).body
            if isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and t.id == 'HEAD' for t in n.targets))


class CalendarViewTests(unittest.TestCase):
    def test_more_expands_hidden_tasks_without_date_registration_link(self):
        from html.parser import HTMLParser
        records=[]
        for index in range(5):
            record={k:'' for k in HEAD}
            record.update({'통합ID':f'task-{index}','업무명':f'업무 {index}',
                           '마감일':'2026-11-12','진행상태':'미진행'})
            records.append([record[k] for k in HEAD])
        self.service.spreadsheets.return_value.values.return_value.get.return_value.execute.return_value={'values':[HEAD]+records}
        at=self.app('2026-11-01')
        html=next(x.value for x in at.markdown if '<div class="cal-shell">' in x.value)
        class Overflow(HTMLParser):
            def __init__(self):
                super().__init__()
                self.inside=False
                self.links=[]
                self.summaries=0
            def handle_starttag(self,tag,attrs):
                attrs=dict(attrs)
                if tag=='details' and attrs.get('class')=='cal-overflow':
                    self.inside=True
                if self.inside and tag=='summary':
                    self.summaries+=1
                if self.inside and tag=='a':
                    self.links.append(attrs['href'])
            def handle_endtag(self,tag):
                if tag=='details':
                    self.inside=False
        parsed=Overflow()
        parsed.feed(html)
        self.assertEqual(parsed.summaries,1)
        self.assertEqual(parsed.links,[
            '?calendar_task=task-3&calendar_month=2026-11-01',
            '?calendar_task=task-4&calendar_month=2026-11-01'])
        self.assertIn('+ 2건 더보기',html)
        self.assertFalse(any(x.label=='업무명 *' for x in at.text_input))

    def test_calendar_colors_identify_owners_independently_of_status(self):
        records=[]
        for name,status in [('김주원','완료'),('이상인','미진행'),('조인환','진행중')]:
            record={k:'' for k in HEAD}
            record.update({'통합ID':name,'업무명':name+' 업무','담당자':name,'마감일':'2026-11-12','진행상태':status,'진행률':'100' if status=='완료' else '20'})
            records.append([record[k] for k in HEAD])
        self.service.spreadsheets.return_value.values.return_value.get.return_value.execute.return_value={'values':[HEAD]+records}
        at=self.app('2026-11-01')
        html=next(x.value for x in at.markdown if '<div class="cal-shell">' in x.value)
        from html.parser import HTMLParser
        class Events(HTMLParser):
            def __init__(self):
                super().__init__()
                self.events={}
            def handle_starttag(self,tag,attrs):
                attrs=dict(attrs)
                if tag=='a' and attrs.get('class')=='cal-event':
                    self.events[attrs['title'].split(' · ')[1]]=attrs['style']
        events=Events()
        events.feed(html)
        for name,color in [('김주원','#eab308'),('이상인','#22a05a'),('조인환','#3b82f6')]:
            self.assertIn(color,events.events[name])
        self.assertIn('✓ 김주원 업무',html)

    def setUp(self):
        st.cache_resource.clear()
        self.service = MagicMock()
        self.service.spreadsheets.return_value.get.return_value.execute.return_value = {'sheets':[{'properties':{'title':'통합업무'}}]}
        self.service.spreadsheets.return_value.values.return_value.get.return_value.execute.return_value = {'values':[HEAD]}
        self.auth = patch('google.oauth2.service_account.Credentials.from_service_account_info', return_value=MagicMock())
        self.build = patch('googleapiclient.discovery.build', return_value=self.service)
        self.auth.start()
        self.build.start()
        self.addCleanup(self.auth.stop)
        self.addCleanup(self.build.stop)
        self.addCleanup(st.cache_resource.clear)

    def app(self, month, day=None):
        at = AppTest.from_file(str(APP))
        at.secrets['gcp_service_account'] = {'offline_test':True}
        at.query_params['calendar_month'] = month
        if day:
            at.query_params['calendar_date'] = day
        at.run(timeout=30)
        self.assertFalse(at.exception, [e.message for e in at.exception])
        return at

    def redraw(self, previous, page='🗓️ 달력'):
        # Streamlit 1.50 AppTest retains old fragment/dialog nodes after rerun.
        # Rehydrate the persisted application state in a fresh renderer to check
        # the resulting page rather than those stale test-runner nodes.
        at=AppTest.from_file(str(APP))
        at.secrets['gcp_service_account']={'offline_test':True}
        at.query_params.update(previous.query_params)
        for key in ('month','calendar_new_open','task_edit_open','task_new_panel_closed','task_new_form_version'):
            if key in previous.session_state:
                at.session_state[key]=previous.session_state[key]
        at.run(timeout=30)
        if page!='🗓️ 달력':
            at.sidebar.radio[0].set_value(page).run(timeout=30)
        self.assertFalse(at.exception)
        return at

    def test_november_registration_keeps_november_after_save(self):
        at = self.app('2026-11-01', '2026-11-12')
        self.assertEqual(at.session_state['month'], date(2026,11,1))
        calendar_html = [x.value for x in at.markdown if '<div class="cal-shell">' in x.value]
        self.assertTrue(calendar_html)
        self.assertTrue(all('calendar_month=2026-11-01' in html for html in calendar_html))
        next(x for x in reversed(list(at.text_input)) if x.label == '업무명 *').set_value('11월 업무')
        next(x for x in reversed(list(at.button)) if x.label == '저장').click().run(timeout=30)
        self.assertFalse(at.exception)
        self.assertEqual(at.session_state['month'], date(2026,11,1))
        self.assertNotIn('calendar_date', at.query_params)
        self.assertIn('2026-11-01', at.query_params['calendar_month'])
        saved = self.service.spreadsheets.return_value.values.return_value.append.call_args.kwargs['body']['values'][0]
        record = dict(zip(HEAD,saved))
        self.assertEqual(record['마감일'], '2026-11-12')
        self.assertEqual(record['업무명'], '｢공통｣ 11월 업무')
        self.assertTrue(any('일정이 등록되었습니다' in x.value for x in at.success))
        self.assertFalse(any(x.label == '업무명 *' for x in self.redraw(at).text_input))

    def test_add_button_dialog_closes_after_success(self):
        at = self.app('2026-11-01')
        next(b for b in at.button if b.label=='＋ 일정 추가').click().run(timeout=30)
        self.assertTrue(at.session_state['calendar_new_open'])
        next(x for x in at.text_input if x.label=='업무명 *').set_value('새 일정')
        next(b for b in at.button if b.label=='저장').click().run(timeout=30)
        self.assertFalse(at.exception)
        self.assertNotIn('calendar_new_open', at.session_state)
        self.assertFalse(any(x.label=='업무명 *' for x in self.redraw(at).text_input))
        self.assertEqual(at.session_state['month'],date(2026,11,1))

    def test_failed_save_keeps_date_dialog_and_entered_values(self):
        at = self.app('2026-11-01','2026-11-12')
        self.service.spreadsheets.return_value.values.return_value.append.return_value.execute.side_effect=RuntimeError('offline save failure')
        next(x for x in at.text_input if x.label=='업무명 *').set_value('다시 저장할 일정')
        next(b for b in at.button if b.label=='저장').click().run(timeout=30)
        self.assertFalse(at.exception)
        self.assertIn('calendar_date',at.query_params)
        self.assertTrue(any('저장 실패' in x.value for x in at.error))
        self.assertEqual(next(x for x in at.text_input if x.label=='업무명 *').value,'다시 저장할 일정')

    def existing_record(self):
        record={k:'' for k in HEAD}
        record.update({'통합ID':'existing','업무명':'｢공통｣ 기존 업무','시작일':'2026-11-12','마감일':'2026-11-12','진행상태':'미진행','우선순위':'보통','진행률':'0','업무구분':'일반업무'})
        self.service.spreadsheets.return_value.values.return_value.get.return_value.execute.return_value={'values':[HEAD,[record[k] for k in HEAD]]}

    def test_calendar_edit_closes_after_save(self):
        self.existing_record()
        at=self.app('2026-11-01')
        at.query_params['calendar_task']='existing'
        at.run(timeout=30)
        self.assertFalse(at.exception)
        next(x for x in at.text_input if x.label=='업무명 *').set_value('수정 완료')
        next(b for b in at.button if b.label=='저장').click().run(timeout=30)
        self.assertFalse(at.exception)
        self.assertNotIn('calendar_task',at.query_params)
        self.assertFalse(any(x.label=='업무명 *' for x in self.redraw(at).text_input))
        self.assertTrue(any('수정되었습니다' in x.value for x in at.success))

    def test_task_list_edit_and_new_panel_close_after_save(self):
        self.existing_record()
        at=self.app('2026-11-01')
        at.sidebar.radio[0].set_value('📋 업무현황').run(timeout=30)
        at.button(key='open_task_edit_existing').click().run(timeout=30)
        self.assertEqual(at.session_state['task_edit_open'],'existing')
        next(b for b in at.button if b.label=='✓ 변경사항 저장하기').click().run(timeout=30)
        self.assertFalse(at.exception)
        self.assertNotIn('task_edit_open',at.session_state)
        at=self.redraw(at,'📋 업무현황')
        self.assertFalse(any(b.label=='✓ 변경사항 저장하기' for b in at.button))
        next(x for x in at.text_input if x.label=='업무명 *').set_value('새 업무')
        next(b for b in at.button if b.label=='저장').click().run(timeout=30)
        self.assertFalse(at.exception)
        self.assertTrue(at.session_state['task_new_panel_closed'])
        at=self.redraw(at,'📋 업무현황')
        self.assertFalse(any(x.label=='업무명 *' for x in at.text_input))
        next(b for b in at.button if b.label=='＋ 새 업무 작성').click().run(timeout=30)
        self.assertTrue(any(x.label=='업무명 *' for x in at.text_input))

    def test_adjacent_month_day_preserves_displayed_december(self):
        at = self.app('2026-12-01','2027-01-02')
        self.assertEqual(at.session_state['month'],date(2026,12,1))
        inputs = [x for x in at.date_input if x.label in ('시작일','마감일')]
        self.assertTrue(all(x.value == date(2027,1,2) for x in inputs[-2:]))

    def test_month_navigation_updates_persistent_url(self):
        at = self.app('2026-11-01')
        at.button(key='month_next').click().run(timeout=30)
        self.assertFalse(at.exception)
        self.assertEqual(at.session_state['month'],date(2026,12,1))
        self.assertIn('2026-12-01',at.query_params['calendar_month'])
        at.button(key='month_prev').click().run(timeout=30)
        self.assertEqual(at.session_state['month'],date(2026,11,1))


if __name__ == '__main__':
    unittest.main()

class FixedCalendarViewTests(unittest.TestCase):
    setUp = CalendarViewTests.setUp
    app = CalendarViewTests.app
    existing_record = CalendarViewTests.existing_record

    def test_fixed_calendar_projection_and_edit_anchor(self):
        self.existing_record()
        values=self.service.spreadsheets.return_value.values.return_value.get.return_value.execute.return_value['values']
        values[1][HEAD.index('원본시트')]='고정업무'
        values[1][HEAD.index('마감일')]='2026-09-14'
        values[1][HEAD.index('시작일')]='2026-09-14'
        at=self.app('2026-11-01')
        at.sidebar.radio[0].set_value('🔁 고정업무').run(timeout=30)
        self.assertFalse(at.exception)
        html=next(x.value for x in at.markdown if '<div class="cal-shell">' in x.value)
        self.assertIn('fixed=1&amp;calendar_task=existing',html)
        from html.parser import HTMLParser
        class Days(HTMLParser):
            def __init__(self):
                super().__init__(); self.day=''; self.events=[]
            def handle_starttag(self,tag,attrs):
                attrs=dict(attrs)
                if tag=='a' and 'calendar_date=' in attrs.get('href',''):
                    self.day=attrs['href'].split('calendar_date=')[1].split('&')[0]
                if attrs.get('class')=='cal-event':self.events.append(self.day)
        parsed=Days();parsed.feed(html)
        self.assertEqual(parsed.events,['2026-11-16'])
        at.query_params['calendar_task']='existing'
        at.run(timeout=30)
        self.assertEqual(next(x for x in at.date_input if x.label=='마감일').value,date(2026,9,14))

    def test_new_fixed_task_is_saved_as_template(self):
        at=self.app('2026-11-01')
        at.sidebar.radio[0].set_value('🔁 고정업무').run(timeout=30)
        next(b for b in at.button if b.label=='＋ 일정 추가').click().run(timeout=30)
        next(x for x in at.text_input if x.label=='업무명 *').set_value('월간 정산')
        next(b for b in at.button if b.label=='저장').click().run(timeout=30)
        self.assertFalse(at.exception)
        saved=self.service.spreadsheets.return_value.values.return_value.append.call_args.kwargs['body']['values'][0]
        self.assertEqual(dict(zip(HEAD,saved))['원본시트'],'고정업무')

class CalendarDeleteTests(unittest.TestCase):
    setUp = CalendarViewTests.setUp
    app = CalendarViewTests.app
    existing_record = CalendarViewTests.existing_record

    def detail(self, fixed=False):
        self.existing_record()
        if fixed:
            rows=self.service.spreadsheets.return_value.values.return_value.get.return_value.execute.return_value['values']
            rows[1][HEAD.index('원본시트')]='고정업무'
        self.service.spreadsheets.return_value.get.return_value.execute.return_value={'sheets':[{'properties':{'title':'통합업무','sheetId':42}}]}
        at=self.app('2026-11-01')
        if fixed:at.sidebar.radio[0].set_value('🔁 고정업무').run(timeout=30)
        at.query_params['calendar_task']='existing'
        at.run(timeout=30)
        self.assertFalse(at.exception)
        return at

    def test_delete_requires_confirmation_then_deletes_exact_row(self):
        at=self.detail()
        self.assertTrue(at.button(key='calendar_delete_existing').disabled)
        self.service.spreadsheets.return_value.batchUpdate.assert_not_called()
        at.checkbox(key='calendar_delete_confirm_existing').check().run(timeout=30)
        at.button(key='calendar_delete_existing').click().run(timeout=30)
        self.assertFalse(at.exception)
        body=self.service.spreadsheets.return_value.batchUpdate.call_args.kwargs['body']
        self.assertEqual(body,{'requests':[{'deleteDimension':{'range':{'sheetId':42,'dimension':'ROWS','startIndex':1,'endIndex':2}}}]})
        self.assertNotIn('calendar_task',at.query_params)
        self.assertTrue(any('일정이 삭제' in x.value for x in at.success))
        self.assertEqual(at.session_state['month'],date(2026,11,1))

    def test_fixed_task_warns_all_repetitions_and_deletes_unfinished_task(self):
        at=self.detail(fixed=True)
        self.assertTrue(any('모든 달의 반복' in x.value for x in at.warning))
        at.checkbox(key='calendar_delete_confirm_existing').check().run(timeout=30)
        at.button(key='calendar_delete_existing').click().run(timeout=30)
        self.assertFalse(at.exception)
        self.service.spreadsheets.return_value.batchUpdate.assert_called_once()
        self.assertNotIn('calendar_task',at.query_params)
        self.assertEqual(at.query_params['fixed'],['1'])

    def test_failed_delete_keeps_detail_open(self):
        at=self.detail()
        self.service.spreadsheets.return_value.batchUpdate.return_value.execute.side_effect=RuntimeError('write failed')
        at.checkbox(key='calendar_delete_confirm_existing').check().run(timeout=30)
        at.button(key='calendar_delete_existing').click().run(timeout=30)
        self.assertFalse(at.exception)
        self.assertIn('calendar_task',at.query_params)
        self.assertTrue(any('삭제 실패' in x.value for x in at.error))

    def test_duplicate_id_prevents_delete(self):
        at=self.detail()
        values=self.service.spreadsheets.return_value.values.return_value.get.return_value.execute.return_value['values']
        at.checkbox(key='calendar_delete_confirm_existing').check().run(timeout=30)
        self.service.spreadsheets.return_value.values.return_value.get.return_value.execute.side_effect=[{'values':values},{'values':values},{'values':values+[list(values[1])]}]
        at.button(key='calendar_delete_existing').click().run(timeout=30)
        self.assertFalse(at.exception)
        self.service.spreadsheets.return_value.batchUpdate.assert_not_called()
        self.assertTrue(any('ID가 중복' in x.value for x in at.error))

class WeeklyMeetingTests(unittest.TestCase):
    setUp=CalendarViewTests.setUp
    app=CalendarViewTests.app

    def test_shortcut_saves_shared_friday_weekly_task(self):
        at=self.app('2026-11-01')
        at.sidebar.radio[0].set_value('🔁 고정업무').run(timeout=30)
        at.button(key='add_weekly_meeting').click().run(timeout=30)
        self.assertFalse(at.exception)
        values=self.service.spreadsheets.return_value.values.return_value.append.call_args.kwargs['body']['values'][0]
        record=dict(zip(HEAD,values))
        self.assertEqual(record['업무명'],'｢공통｣ 주간회의 작성 및 제출')
        self.assertEqual(record['담당자'],'전체')
        self.assertEqual(date.fromisoformat(record['마감일']).weekday(),4)
        self.assertTrue(record['원본ID'].startswith('weekly:'))
        self.assertEqual(record['원본시트'],'고정업무')
        self.service.spreadsheets.return_value.values.return_value.get.return_value.execute.return_value={'values':[HEAD,values]}
        at.button(key='add_weekly_meeting').click().run(timeout=30)
        self.assertFalse(at.exception)
        self.service.spreadsheets.return_value.values.return_value.append.assert_called_once()
        self.assertTrue(any('이미 등록' in x.value for x in at.info))

    def test_weekly_form_preserves_frequency_when_edited(self):
        record={field:'' for field in HEAD}
        record.update({'통합ID':'weekly-task','원본시트':'고정업무','원본ID':'weekly:abc',
                       '업무명':'｢공통｣ 주간회의 작성 및 제출','시작일':'2026-11-13','마감일':'2026-11-13'})
        self.service.spreadsheets.return_value.values.return_value.get.return_value.execute.return_value={'values':[HEAD,[record[field] for field in HEAD]]}
        at=self.app('2026-11-01')
        at.sidebar.radio[0].set_value('🔁 고정업무').run(timeout=30)
        at.query_params['calendar_task']='weekly-task'
        at.run(timeout=30)
        self.assertEqual(next(x for x in at.selectbox if x.label=='반복 주기').value,'매주')
        next(x for x in at.button if x.label=='저장').click().run(timeout=30)
        self.assertFalse(at.exception)
        saved=self.service.spreadsheets.return_value.values.return_value.update.call_args.kwargs['body']['values'][0]
        self.assertEqual(dict(zip(HEAD,saved))['원본ID'],'weekly:abc')
