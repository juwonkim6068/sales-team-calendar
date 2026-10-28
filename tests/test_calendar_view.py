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
