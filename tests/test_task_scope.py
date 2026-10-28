import ast
from pathlib import Path
import unittest

from streamlit.testing.v1 import AppTest

SOURCE = Path(__file__).resolve().parents[1] / 'app.py'
TREE = ast.parse(SOURCE.read_text())
NAMES = {'safe', 'dt', 'task_title_parts', 'task_title_with_kind', 'form'}
CONSTANTS = {'HEAD', 'STATES', 'CATS'}
NODES = [n for n in TREE.body if isinstance(n, (ast.Import, ast.ImportFrom))
         or isinstance(n, ast.FunctionDef) and n.name in NAMES
         or isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and t.id in CONSTANTS for t in n.targets)]
FORM_SOURCE = ast.unparse(ast.Module(body=NODES, type_ignores=[]))
FORM_SOURCE += '\ndef save_record(svc, record, old_id=None):\n st.session_state["saved"] = record\n st.session_state["saved_old_id"] = old_id\n'


class TaskScopeTests(unittest.TestCase):
    def form(self, existing=None):
        return AppTest.from_string(FORM_SOURCE + f'\nform(None,["김주원","전체"],existing={existing!r},key="test")').run()

    def test_new_personal_task_with_everyone_owner(self):
        at = self.form()
        self.assertFalse(at.exception)
        owner = next(x for x in at.selectbox if x.label == '담당자')
        self.assertEqual(owner.options.count('전체'), 1)
        owner.select('전체')
        at.radio[0].set_value('개인')
        at.text_input[0].set_value('거래처 방문')
        at.button[0].click().run()
        self.assertFalse(at.exception)
        self.assertEqual(at.session_state['saved']['업무명'], '｢개인｣ 거래처 방문')
        self.assertEqual(at.session_state['saved']['담당자'], '전체')

    def test_edit_switches_kind_without_duplicating_label(self):
        at = self.form({'통합ID':'original','업무명':'｢개인｣ 월말 정산','담당자':'전체'})
        self.assertEqual(at.text_input[0].value, '월말 정산')
        self.assertEqual(at.radio[0].value, '개인')
        at.radio[0].set_value('공통')
        at.button[0].click().run()
        self.assertFalse(at.exception)
        self.assertEqual(at.session_state['saved']['업무명'], '｢공통｣ 월말 정산')
        self.assertEqual(at.session_state['saved_old_id'], 'original')

    def test_legacy_title_is_preserved_until_saved(self):
        at = self.form({'업무명':'기존 업무'})
        self.assertEqual(at.text_input[0].value, '기존 업무')
        self.assertEqual(at.radio[0].value, '공통')
        self.assertNotIn('saved', at.session_state)

    def test_prefix_only_is_not_a_valid_task_name(self):
        at = self.form()
        at.text_input[0].set_value('｢개인｣ ｢공통｣ ')
        at.button[0].click().run()
        self.assertFalse(at.exception)
        self.assertTrue(any('업무명을 입력' in e.value for e in at.error))
        self.assertNotIn('saved', at.session_state)


if __name__ == '__main__':
    unittest.main()
