"""Execute the production payment handler against a real temporary SQLite database.

No Telegram network calls or real charges are made.
"""
import ast
import logging
import os
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock, patch
from app import database as db


class PaymentDeliveryTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        env = patch.dict(os.environ, {'DATABASE_PATH': str(Path(self.temp.name) / 'test.db')})
        env.start()
        self.addCleanup(env.stop)
        db.init_db()
        tree = ast.parse((Path(__file__).resolve().parents[1] / 'app/bot.py').read_text())
        handler, = [n for n in ast.walk(tree) if isinstance(n, ast.AsyncFunctionDef) and n.name == 'successful_payment']
        handler.decorator_list = []
        module = ast.Module(body=[ast.ImportFrom(module='__future__', names=[ast.alias(name='annotations')], level=0), handler], type_ignores=[])
        ast.fix_missing_locations(module)
        namespace = dict(upsert_user=db.upsert_user, activate_star_subscription=db.activate_star_subscription,
                         logger=logging.getLogger('payment-test'))
        exec(compile(module, '<production payment handler>', 'exec'), namespace)
        self.handler = namespace['successful_payment']

    def message(self, **changes):
        fields = dict(currency='XTR', invoice_payload='antiscam:pro:monthly:v1', total_amount=125,
                      telegram_payment_charge_id='test-only-charge')
        fields.update(changes)
        return SimpleNamespace(from_user=SimpleNamespace(id=777, username='test'),
                               successful_payment=SimpleNamespace(**fields), answer=AsyncMock())

    async def test_delivery_and_duplicate_do_not_extend_twice(self):
        message = self.message()
        await self.handler(message)
        with db._connect() as conn:
            before = conn.execute('SELECT expires_at FROM subscriptions WHERE telegram_id=777').fetchone()[0]
        await self.handler(message)
        with db._connect() as conn:
            after = conn.execute('SELECT expires_at FROM subscriptions WHERE telegram_id=777').fetchone()[0]
            self.assertEqual(conn.execute('SELECT COUNT(*) FROM star_charges').fetchone()[0], 1)
        self.assertEqual(before, after)
        self.assertIn('already processed', message.answer.call_args.args[0])

    async def test_refunded_payment_replay_does_not_claim_active_access(self):
        message = self.message()
        await self.handler(message)
        self.assertTrue(db.record_star_refund('test-only-charge'))
        await self.handler(message)
        self.assertTrue(db.get_star_charge('test-only-charge')['refunded'])
        self.assertNotIn('remains active', message.answer.call_args.args[0])

    async def test_paid_update_delivered_even_after_payments_disabled(self):
        with patch.dict(os.environ, {'PAYMENTS_MODE': 'disabled', 'STARS_MONTHLY_PRICE': '0'}):
            await self.handler(self.message())
        self.assertIsNotNone(db.get_star_charge('test-only-charge'))

    async def test_invalid_payment_does_not_create_entitlement(self):
        for changes in [dict(currency='USD'), dict(total_amount=0), dict(invoice_payload='other'), dict(telegram_payment_charge_id='')]:
            message = self.message(**changes)
            await self.handler(message)
            self.assertIn('support review', message.answer.call_args.args[0])
        with db._connect() as conn:
            self.assertEqual(conn.execute('SELECT COUNT(*) FROM subscriptions').fetchone()[0], 0)
