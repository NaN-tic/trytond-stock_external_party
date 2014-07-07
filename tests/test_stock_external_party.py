#!/usr/bin/env python
# The COPYRIGHT file at the top level of this repository contains the full
# copyright notices and license terms.
from decimal import Decimal
import datetime
from dateutil.relativedelta import relativedelta
import unittest
import trytond.tests.test_tryton
from trytond.tests.test_tryton import POOL, DB_NAME, USER, CONTEXT, test_view,\
    test_depends
from trytond.transaction import Transaction
from trytond.exceptions import UserError


class TestCase(unittest.TestCase):
    'Test module'

    def setUp(self):
        trytond.tests.test_tryton.install_module('stock_external_party')
        self.template = POOL.get('product.template')
        self.product = POOL.get('product.product')
        self.party = POOL.get('party.party')
        self.category = POOL.get('product.category')
        self.uom = POOL.get('product.uom')
        self.location = POOL.get('stock.location')
        self.move = POOL.get('stock.move')
        self.shipment = POOL.get('stock.shipment.external')
        self.company = POOL.get('company.company')
        self.user = POOL.get('res.user')
        self.period = POOL.get('stock.period')
        self.inventory = POOL.get('stock.inventory')

    def test0005views(self):
        'Test views'
        test_view('stock_external_party')

    def test0006depends(self):
        'Test depends'
        test_depends()

    def test0010stock_external(self):
        'Test stock external'
        with Transaction().start(DB_NAME, USER,
                context=CONTEXT) as transaction:
            category, = self.category.create([{
                        'name': 'Test products_by_location',
                        }])
            kg, = self.uom.search([('name', '=', 'Kilogram')])
            g, = self.uom.search([('name', '=', 'Gram')])
            template, = self.template.create([{
                        'name': 'Test products_by_location',
                        'type': 'goods',
                        'list_price': Decimal(0),
                        'cost_price': Decimal(0),
                        'category': category.id,
                        'cost_price_method': 'fixed',
                        'default_uom': kg.id,
                        }])
            product, = self.product.create([{
                        'template': template.id,
                        }])
            supplier, = self.location.search([('code', '=', 'SUP')])
            customer, = self.location.search([('code', '=', 'CUS')])
            storage, = self.location.search([('code', '=', 'STO')])
            company, = self.company.search([
                    ('rec_name', '=', 'Dunder Mifflin'),
                    ])
            currency = company.currency
            self.user.write([self.user(USER)], {
                'main_company': company.id,
                'company': company.id,
                })

            party, = self.party.create([{
                    'name': 'Customer',
                    }])
            self.assertEqual(party.customer_location, customer)
            self.assertEqual(party.supplier_location, supplier)

            #Recieve products from customer
            move, = self.move.create([{
                        'product': product.id,
                        'uom': kg.id,
                        'quantity': 5,
                        'from_location': customer.id,
                        'to_location': storage.id,
                        'company': company.id,
                        'unit_price': Decimal('1'),
                        'currency': currency.id,
                        'party_used': party.id,
                        }])
            self.move.do([move])

            with transaction.set_context(products=[product.id]):
                party = self.party(party.id)
                self.assertEqual(party.quantity, 5.0)

            #Send products to customer another time
            move, = self.move.create([{
                        'product': product.id,
                        'uom': kg.id,
                        'quantity': 5,
                        'from_location': storage.id,
                        'to_location': customer.id,
                        'company': company.id,
                        'unit_price': Decimal('1'),
                        'currency': currency.id,
                        'party_used': party.id,
                        }])
            with self.assertRaises(UserError):
                self.move.do([move])

            self.move.write([move], {'party_used': None})

            shipment, = self.shipment.create([{
                        'company': company.id,
                        'party': party.id,
                        'from_location': storage.id,
                        'to_location': customer.id,
                        'moves': [('add', [move])],
                        }])

            #Test that party is written to moves
            self.shipment.wait([shipment])
            move = self.move(move.id)
            self.assertEqual(move.party_used, party)

            self.assertEqual(self.shipment.assign_try([shipment]), True)
            self.shipment.done([shipment])

            move = self.move(move.id)
            self.assertEqual(move.state, 'done')

            with transaction.set_context(products=[product.id]):
                party = self.party(party.id)
                self.assertEqual(party.quantity, 0.0)

    def test0020period(self):
        'Test period'
        with Transaction().start(DB_NAME, USER, context=CONTEXT):
            unit, = self.uom.search([('name', '=', 'Unit')])
            template, = self.template.create([{
                        'name': 'Test period',
                        'type': 'goods',
                        'cost_price_method': 'fixed',
                        'default_uom': unit.id,
                        'list_price': Decimal(0),
                        'cost_price': Decimal(0),
                        }])
            product, = self.product.create([{
                        'template': template.id,
                        }])
            supplier, = self.location.search([('code', '=', 'SUP')])
            storage, = self.location.search([('code', '=', 'STO')])
            company, = self.company.search([
                    ('rec_name', '=', 'Dunder Mifflin'),
                    ])
            currency = company.currency
            self.user.write([self.user(USER)], {
                'main_company': company.id,
                'company': company.id,
                })

            party1, party2 = self.party.create([{
                        'name': 'Party 1',
                        }, {
                        'name': 'Party 2',
                        }])

            today = datetime.date.today()

            moves = self.move.create([{
                        'product': product.id,
                        'party': party1.id,
                        'uom': unit.id,
                        'quantity': 5,
                        'from_location': supplier.id,
                        'to_location': storage.id,
                        'planned_date': today - relativedelta(days=1),
                        'effective_date': today - relativedelta(days=1),
                        'company': company.id,
                        'unit_price': Decimal('1'),
                        'currency': currency.id,
                        }, {
                        'product': product.id,
                        'party': party2.id,
                        'uom': unit.id,
                        'quantity': 10,
                        'from_location': supplier.id,
                        'to_location': storage.id,
                        'planned_date': today - relativedelta(days=1),
                        'effective_date': today - relativedelta(days=1),
                        'company': company.id,
                        'unit_price': Decimal('1'),
                        'currency': currency.id,
                        }, {
                        'product': product.id,
                        'party': None,
                        'uom': unit.id,
                        'quantity': 3,
                        'from_location': supplier.id,
                        'to_location': storage.id,
                        'planned_date': today - relativedelta(days=1),
                        'effective_date': today - relativedelta(days=1),
                        'company': company.id,
                        'unit_price': Decimal('1'),
                        'currency': currency.id,
                        }])
            self.move.do(moves)

            period, = self.period.create([{
                        'date': today - relativedelta(days=1),
                        'company': company.id,
                        }])
            self.period.close([period])
            self.assertEqual(period.state, 'closed')

            quantities = {
                supplier: -18,
                storage: 18,
                }
            for cache in period.caches:
                self.assertEqual(cache.product, product)
                self.assertEqual(cache.internal_quantity,
                    quantities[cache.location])

            quantities = {
                (supplier, party1): -5,
                (storage, party1): 5,
                (supplier, party2): -10,
                (storage, party2): 10,
                (supplier, None): -3,
                (storage, None): 3,
                }
            for party_cache in period.party_caches:
                self.assertEqual(party_cache.product, product)
                self.assertEqual(party_cache.internal_quantity,
                    quantities[(party_cache.location, party_cache.party)])

    def test0030inventory(self):
        'Test inventory'
        with Transaction().start(DB_NAME, USER,
                context=CONTEXT) as transaction:
            unit, = self.uom.search([('name', '=', 'Unit')])
            template, = self.template.create([{
                        'name': 'Test period',
                        'type': 'goods',
                        'cost_price_method': 'fixed',
                        'default_uom': unit.id,
                        'list_price': Decimal(0),
                        'cost_price': Decimal(0),
                        }])
            product, = self.product.create([{
                        'template': template.id,
                        }])
            lost_found, = self.location.search([('type', '=', 'lost_found')])
            storage, = self.location.search([('code', '=', 'STO')])
            company, = self.company.search([
                    ('rec_name', '=', 'Dunder Mifflin'),
                    ])
            self.user.write([self.user(USER)], {
                'main_company': company.id,
                'company': company.id,
                })

            party, = self.party.create([{
                        'name': 'Party',
                        }])

            with transaction.set_context(products=[product.id]):
                party = self.party(party.id)
                self.assertEqual(party.quantity, 0.0)

            inventory, = self.inventory.create([{
                        'company': company.id,
                        'location': storage.id,
                        'lost_found': lost_found.id,
                        'date': datetime.date.today(),
                        'lines': [('create', [{
                                        'product': product.id,
                                        'party': party.id,
                                        'quantity': 5.0,
                                        'uom': unit.id,
                                        }])],
                        }])
            self.inventory.confirm([inventory])

            with transaction.set_context(products=[product.id]):
                party = self.party(party.id)
                self.assertEqual(party.quantity, 5.0)

            inventory, = self.inventory.create([{
                        'company': company.id,
                        'location': storage.id,
                        'lost_found': lost_found.id,
                        'date': datetime.date.today(),
                        }])
            self.inventory.complete_lines([inventory])
            line, = inventory.lines
            self.assertEqual(line.product, product)
            self.assertEqual(line.party, party)
            self.assertEqual(line.quantity, 5.0)


def suite():
    suite = trytond.tests.test_tryton.suite()
    from trytond.modules.company.tests import test_company
    for test in test_company.suite():
        if test not in suite:
            suite.addTest(test)
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(TestCase))
    return suite
