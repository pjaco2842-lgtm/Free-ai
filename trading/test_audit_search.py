import copy
from pathlib import Path
import subprocess
import sys
import unittest

import numpy as np

import account
import bots
import desk
import execution
import paper_oracle
from audit_search import feature_arrays, outcomes, walk_sessions
from mine26k import day_trade, model_pred, spec_legs


class AuditChecks(unittest.TestCase):
    def test_both_brackets_touched_stop_wins_for_both_sides(self):
        o = np.array([100.0])
        h = np.array([102.0])
        l = np.array([98.0])
        c = np.array([101.0])
        atr = np.array([1.0])
        for side in (1, -1):
            actual = outcomes(o, h, l, c, atr, .25, 5, .5, 1, 1, side)
            self.assertAlmostEqual(actual[0], -8.5)

    def test_current_bar_does_not_change_features(self):
        prices = np.arange(1., 31.)
        before = feature_arrays(prices, prices + 1, prices - 1, prices, np.ones(30))
        changed = prices.copy()
        changed[20] = 9999
        after = feature_arrays(changed, prices + 1, prices - 1, changed, np.ones(30))
        for key in before:
            np.testing.assert_allclose(before[key][:21], after[key][:21], equal_nan=True,
                                       err_msg=key)

    def test_nontrading_day_counts_and_consistency_requires_continuation(self):
        pnl = np.array([800., 0., 400., 800.])
        taken = np.array([1, 0, 1, 1], dtype=bool)
        result = walk_sessions(pnl, taken, ['a', 'b', 'c', 'd'], [0])
        self.assertEqual(result['pass'], 1)
        self.assertEqual(result['pass3'], 0)
        self.assertEqual(result['median_pass_sessions'], 4)

    def test_trailing_floor_uses_previous_close(self):
        result = walk_sessions(np.array([600., -1050.]), np.array([1, 1], dtype=bool),
                               ['a', 'b'], [0])
        self.assertEqual(result['breach'], 1)

    def test_model_excludes_nonfinite_training_features(self):
        x = np.arange(305., dtype=float).reshape(-1, 1)
        y = x[:, 0] * 2
        years = np.full(305, 2009)
        years[-2:] = 2010
        x[0, 0] = np.nan
        x[1, 0] = np.inf
        x[-1, 0] = np.nan
        pred = model_pred(x, y, years)
        self.assertTrue(np.isfinite(pred[-2]))
        self.assertTrue(np.isnan(pred[-1]))
        # Changing a current year's label cannot influence its predictions.
        y[-2] = 999999
        self.assertEqual(pred[-2], model_pred(x, y, years)[-2])

    def test_account_floor_and_missing_close_history(self):
        self.assertEqual(account.floor_for(25000), 24000)
        self.assertEqual(account.floor_for(25500), 24500)
        self.assertEqual(account.floor_for(26100), 25100)
        self.assertEqual(account.floor_for(28000), 25100)
        self.assertEqual(account.buffer_now({'equity': 26500}), 0)
        self.assertEqual(account.buffer_now({'equity': 26500, 'peak_eod': 25000}), 2500)
        self.assertEqual(account.buffer_now({'equity': 25200, 'peak_eod': 26100}), 100)
        self.assertEqual(account.buffer_now({'equity': 25000, 'peak_eod': float('nan')}), 0)
        self.assertEqual(account.buffer_now({'equity': 25000, 'peak_eod': 0}), 0)
        self.assertEqual(bots.bot12_governor({'equity': 25000}, [])['action'], 'halt')
        self.assertEqual(bots.bot12_governor({'equity': 25000, 'peak_eod': 25000}, [])['action'], 'run')

    def test_unconfigured_optional_rails_do_not_crash(self):
        self.assertIsNone(bots.DAILY_STOP)
        self.assertIsNone(bots.HALT_AT)
        self.assertIsNone(bots.CAUTION_AT)
        ok, reasons = execution.validate({}, state={'open_positions': [], 'day_pnl': 0}, kill=False)
        self.assertFalse(ok)
        self.assertTrue(reasons)

    def test_legacy_paper_entry_points_fail_before_writing(self):
        state = {'last': {}, 'ledger': [], 'equity': 0, 'halted': False}
        before = copy.deepcopy(state)
        with self.assertRaises(SystemExit):
            paper_oracle.step('ES=F', {}, [], state, 0)
        self.assertEqual(state, before)
        with self.assertRaises(SystemExit):
            paper_oracle.watch({}, [], 0)
        with self.assertRaises(SystemExit):
            desk.cycle()
        with self.assertRaises(SystemExit):
            desk.board_cmd()
        with self.assertRaises(SystemExit):
            execution.replay()

    def test_legacy_commands_refuse_to_run_and_preserve_records(self):
        root = Path(__file__).resolve().parent
        paths = [root / 'desk/oracle-state.json', root / 'desk/state.json',
                 root / 'desk/orders.jsonl']
        before = [path.read_bytes() for path in paths]
        for script, args in [('paper_oracle.py', []), ('mine26k.py', []),
                             ('desk.py', ['--cycle']), ('desk.py', ['--board']),
                             ('execution.py', ['--replay'])]:
            p = subprocess.run([sys.executable, str(root / script), *args],
                               capture_output=True, text=True, timeout=15)
            self.assertNotEqual(p.returncode, 0, script)
            self.assertIn('paused' if script != 'mine26k.py' else 'disabled',
                          (p.stdout + p.stderr).lower(), script)
        self.assertEqual(before, [path.read_bytes() for path in paths])

    def test_legacy_claims_target_even_if_target_precedes_dip_entry(self):
        # The path 100 -> 105 -> 95 -> 96 makes a prior-low entry at 95
        # only after the 100 target was reached. The old daily model sees
        # the session high 105 and calls this a winning target fill.
        d = {'o': np.array([100., 100.]), 'h': np.array([100., 105.]),
             'l': np.array([95., 95.]), 'c': np.array([99., 96.]),
             'rng': np.array([5., 10.]), 'atr': np.array([10., 10.]),
             'atr_prev': np.array([np.nan, 10.]), 'sma20': np.array([100., 100.]),
             'sma50': np.array([100., 100.]), 'dow': np.array([0, 1]),
             'hiN': {1: np.array([np.nan, 100.])},
             'loN': {1: np.array([np.nan, 95.])}}
        spec = {'family': 'nday_fade', 'n': 1, 'stop': 1., 'exit': 'tp05',
                'gap': 'with', 'trend': False, 'dow': 'all', 'dir': 'long'}
        actual = day_trade(d, 1, spec, spec_legs(d, spec), 5., .25)
        self.assertEqual(actual['why'], 'target')
        self.assertEqual(actual['exit'], 100.)
        # The path ends at 96 and never returns to 100 after entry.
        self.assertLess(96., actual['exit'])


if __name__ == '__main__':
    unittest.main()
