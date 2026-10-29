import unittest
from unittest.mock import MagicMock, patch
from customer_workspace import watch_customer_changes

class LiveRefreshTests(unittest.TestCase):
 def run_watch(self,state,latest):
  store=MagicMock();store.read_all.return_value=latest
  # Execute initial rendering and one timer tick without waiting 30 seconds.
  def fragment(**kwargs):
   self.assertEqual(kwargs['run_every'],'30s')
   return lambda fn:lambda:(fn(),fn())
  with patch('customer_workspace.st.fragment',side_effect=fragment),patch('customer_workspace.st.session_state',state),patch('customer_workspace.st.caption'),patch('customer_workspace.st.rerun') as rerun:
   watch_customer_changes(store,{'거래처DB':[]})
  return store,rerun
 def test_changed_sheet_refreshes_app(self):
  store,rerun=self.run_watch({}, {'거래처DB':[{'거래처코드':'C1'}]})
  store.read_all.assert_called_once()
  rerun.assert_called_once_with(scope='app')
 def test_open_editor_defers_refresh_and_reads(self):
  store,rerun=self.run_watch({'customer_editor':{'sheet':'거래처DB'}},{})
  store.read_all.assert_not_called();rerun.assert_not_called()
 def test_unchanged_sheet_keeps_current_screen(self):
  store,rerun=self.run_watch({}, {'거래처DB':[]})
  rerun.assert_not_called()
