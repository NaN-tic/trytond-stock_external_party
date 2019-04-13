# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import datetime
import unittest
from dateutil.relativedelta import relativedelta
from decimal import Decimal

import trytond.tests.test_tryton
from trytond.exceptions import UserError
from trytond.pool import Pool
from trytond.tests.test_tryton import ModuleTestCase, with_transaction
from trytond.transaction import Transaction

from trytond.modules.company.tests import create_company, set_company

from mock import Mock


class TestCase(ModuleTestCase):
    'Test module'
    module = 'stock_external_party'

    @with_transaction()
    def test0010stock_external(self):
        'Test stock external'
        pool = Pool()
        Template = pool.get('product.template')
        Product = pool.get('product.product')
        Party = pool.get('party.party')
        Uom = pool.get('product.uom')
        Location = pool.get('stock.location')
        Move = pool.get('stock.move')
        Shipment = pool.get('stock.shipment.external')
        Move.check_origin_types = Mock(return_value=set())
        transaction = Transaction()

        # Create Company
        party = Party(name='Party')
        party.save()
        company = create_company()
        with set_company(company):

            kg, = Uom.search([('name', '=', 'Kilogram')])
            template, = Template.create([{
                        'name': 'Test products_by_location',
                        'type': 'goods',
                        'list_price': Decimal(0),
                        'cost_price_method': 'fixed',
                        'default_uom': kg.id,
                        }])
            product, = Product.create([{
                        'template': template.id,
                        }])
            supplier, = Location.search([('code', '=', 'SUP')])
            customer, = Location.search([('code', '=', 'CUS')])
            storage, = Location.search([('code', '=', 'STO')])

            party, = Party.create([{
                    'name': 'Customer',
                    }])
            self.assertEqual(party.customer_location, customer)
            self.assertEqual(party.supplier_location, supplier)

            # Recieve products from customer
            move, = Move.create([{
                        'product': product.id,
                        'uom': kg.id,
                        'quantity': 5,
                        'from_location': customer.id,
                        'to_location': storage.id,
                        'unit_price': Decimal('1'),
                        'party_used': party.id,
                        }])
            Move.do([move])

            with transaction.set_context(products=[product.id]):
                party = Party(party.id)
                self.assertEqual(party.quantity, 5.0)

            # Send products to customer another time
            move, = Move.create([{
                        'product': product.id,
                        'uom': kg.id,
                        'quantity': 5,
                        'from_location': storage.id,
                        'to_location': customer.id,
                        'unit_price': Decimal('1'),
                        'party_used': party.id,
                        }])
            with self.assertRaises(UserError):
                Move.do([move])

            Move.write([move], {'party_used': None})

            shipment, = Shipment.create([{
                        'party': party.id,
                        'from_location': storage.id,
                        'to_location': customer.id,
                        'moves': [('add', [move])],
                        }])

            # Test that party is written to moves
            Shipment.wait([shipment])
            move = Move(move.id)
            self.assertEqual(move.party_used, party)

            self.assertEqual(Shipment.assign_try([shipment]), True)
            Shipment.done([shipment])

            move = Move(move.id)
            self.assertEqual(move.state, 'done')

            with transaction.set_context(products=[product.id]):
                party = Party(party.id)
                self.assertEqual(party.quantity, 0.0)

    @with_transaction()
    def test0020period(self):
        'Test period'
        pool = Pool()
        Template = pool.get('product.template')
        Product = pool.get('product.product')
        Party = pool.get('party.party')
        Uom = pool.get('product.uom')
        Location = pool.get('stock.location')
        Move = pool.get('stock.move')
        Period = pool.get('stock.period')
        Move.check_origin_types = Mock(return_value=set())

        # Create Company
        party = Party(name='Party')
        party.save()
        company = create_company()
        with set_company(company):
            unit, = Uom.search([('name', '=', 'Unit')])
            template, = Template.create([{
                        'name': 'Test period',
                        'type': 'goods',
                        'cost_price_method': 'fixed',
                        'default_uom': unit.id,
                        'list_price': Decimal(0),
                        }])
            product, = Product.create([{
                        'template': template.id,
                        }])
            supplier, = Location.search([('code', '=', 'SUP')])
            storage, = Location.search([('code', '=', 'STO')])

            party1, party2 = Party.create([{
                        'name': 'Party 1',
                        }, {
                        'name': 'Party 2',
                        }])

            today = datetime.date.today()

            moves = Move.create([{
                        'product': product.id,
                        'party': party1.id,
                        'uom': unit.id,
                        'quantity': 5,
                        'from_location': supplier.id,
                        'to_location': storage.id,
                        'planned_date': today - relativedelta(days=1),
                        'effective_date': today - relativedelta(days=1),
                        'unit_price': Decimal('1'),
                        }, {
                        'product': product.id,
                        'party': party2.id,
                        'uom': unit.id,
                        'quantity': 10,
                        'from_location': supplier.id,
                        'to_location': storage.id,
                        'planned_date': today - relativedelta(days=1),
                        'effective_date': today - relativedelta(days=1),
                        'unit_price': Decimal('1'),
                        }, {
                        'product': product.id,
                        'party': None,
                        'uom': unit.id,
                        'quantity': 3,
                        'from_location': supplier.id,
                        'to_location': storage.id,
                        'planned_date': today - relativedelta(days=1),
                        'effective_date': today - relativedelta(days=1),
                        'unit_price': Decimal('1'),
                        }])
            Move.do(moves)

            period, = Period.create([{
                        'date': today - relativedelta(days=1),
                        'company': company.id,
                        }])
            Period.close([period])
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

    @with_transaction()
    def test0030inventory(self):
        'Test inventory'
        pool = Pool()
        Template = pool.get('product.template')
        Product = pool.get('product.product')
        Party = pool.get('party.party')
        Uom = pool.get('product.uom')
        Location = pool.get('stock.location')
        Move = pool.get('stock.move')
        Inventory = pool.get('stock.inventory')
        Move.check_origin_types = Mock(return_value=set())
        transaction = Transaction()

        # Create Company
        party = Party(name='Party')
        party.save()
        company = create_company()
        with set_company(company):
            unit, = Uom.search([('name', '=', 'Unit')])
            template, = Template.create([{
                        'name': 'Test period',
                        'type': 'goods',
                        'cost_price_method': 'fixed',
                        'default_uom': unit.id,
                        'list_price': Decimal(0),
                        }])
            product, = Product.create([{
                        'template': template.id,
                        }])
            lost_found, = Location.search([('type', '=', 'lost_found')])
            storage, = Location.search([('code', '=', 'STO')])

            party, = Party.create([{
                        'name': 'Party',
                        }])

            with transaction.set_context(products=[product.id]):
                party = Party(party.id)
                self.assertEqual(party.quantity, 0.0)

            yesterday = datetime.date.today() - relativedelta(days=1)

            inventory, = Inventory.create([{
                        'location': storage.id,
                        'lost_found': lost_found.id,
                        'date': yesterday,
                        'lines': [('create', [{
                                        'product': product.id,
                                        'party': party.id,
                                        'quantity': 5.0,
                                        }])],
                        }])
            Inventory.confirm([inventory])

            with transaction.set_context(products=[product.id]):
                party = Party(party.id)
                self.assertEqual(party.quantity, 5.0)

            inventory, = Inventory.create([{
                        'location': storage.id,
                        'lost_found': lost_found.id,
                        'date': datetime.date.today(),
                        }])
            Inventory.complete_lines([inventory])
            inventory = Inventory(inventory.id)

            line, = inventory.lines
            self.assertEqual(line.product, product)
            self.assertEqual(line.party, party)
            self.assertEqual(line.expected_quantity, 5.0)


def suite():
    suite = trytond.tests.test_tryton.suite()
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(TestCase))
    return suite
