#The COPYRIGHT file at the top level of this repository contains the full
#copyright notices and license terms.
import datetime

from trytond.model import ModelView, fields
from trytond.pool import Pool, PoolMeta
from trytond.pyson import PYSONEncoder
from trytond.transaction import Transaction
from trytond.wizard import Wizard, StateView, StateAction, Button
from trytond.modules.stock.move import STATES, DEPENDS
from trytond.modules.stock import StockMixin

__all__ = ['Party', 'Move', 'ShipmentExternal', 'ProductByPartyStart',
    'ProductByParty']
__metaclass__ = PoolMeta


class Party(object, StockMixin):
    __name__ = 'party.party'
    __metaclass__ = PoolMeta
    quantity = fields.Function(fields.Float('Quantity'), 'get_quantity',
        searcher='search_quantity')
    forecast_quantity = fields.Function(fields.Float('Forecast Quantity'),
        'get_quantity', searcher='search_quantity')

    @classmethod
    def get_quantity(cls, parties, name):
        pool = Pool()
        Product = pool.get('product.product')
        transaction = Transaction()
        context = transaction.context
        location_ids = set()
        for party in parties:
            if party.customer_location:
                location_ids.add(party.customer_location.id)
            if party.supplier_location:
                location_ids.add(party.supplier_location.id)
        products = None
        if context.get('products'):
            products = Product.browse(context.get('products'))
        #TODO: Check if we can use dest_location ids to get only moves from
        # and to party location
        pbl = cls._get_quantity(parties, name, list(location_ids), products,
            grouping=('product', 'party'))
        return pbl

    @classmethod
    def search_quantity(cls, name, domain=None):
        location_ids = Transaction().context.get('locations')
        return cls._search_quantity(name, location_ids, domain,
            grouping=('product', 'party_used'))


class Move:
    __name__ = 'stock.move'
    party = fields.Many2One('party.party', 'Party')
    party_used = fields.Function(fields.Many2One('party.party', 'Party',
        states=STATES, depends=DEPENDS), 'get_party_used',
        setter='set_party_used', searcher='search_party_used')
    party_to_check = fields.Function(fields.Many2One('party.party', 'Party'),
        'get_party_to_check')

    @classmethod
    def __setup__(cls):
        super(Move, cls).__setup__()
        cls._error_messages.update({
                'required_shipment': ('Move "%s" has a party defined, so it'
                    ' requires a shipment to be done.'),
                'diferent_party': ('Can not do Move "%s" because it\'s '
                    'from party "%s" and you try to send it to party "%s".'),
                })

    def get_party_used(self, name):
        if self.party:
            return self.party.id

    @classmethod
    def set_party_used(cls, moves, name, value):
        cls.write(moves, {'party': value})

    @classmethod
    def search_party_used(cls, name, clause):
        return [tuple('party',) + tuple(clause[1:])]

    def get_party_to_check(self, name):
        '''
        Returns the party to check if it\'s the same as the party used in
        the move when making the move.

        By default it returns the party of the shipment of the move.
        If no shipment an error is raised.
        '''
        if not self.shipment:
            self.raise_user_error('required_shipment', self.rec_name)
        return self.shipment.party.id

    @classmethod
    def location_types_to_check_party(cls):
        '''
        Returns a list of to locations types that must be checked before
        allowing a move with party defined to be done
        '''
        return ['customer', 'supplier']

    @classmethod
    def do(cls, moves):
        types_to_check = cls.location_types_to_check_party()
        for move in moves:
            if (move.party_used and move.to_location.type in types_to_check
                    and move.party_used != move.party_to_check):
                cls.raise_user_error('diferent_party', (move.rec_name,
                        move.party_used.rec_name,
                        move.shipment.party.rec_name))
        super(Move, cls).do(moves)


class ShipmentExternal:
    __name__ = 'stock.shipment.external'

    @classmethod
    def draft(cls, shipments):
        pool = Pool()
        Move = pool.get('stock.move')
        moves = list(m for s in shipments for m in s.moves)
        Move.write(moves, {'party_used': None})

    @classmethod
    def wait(cls, shipments):
        pool = Pool()
        Move = pool.get('stock.move')
        for shipment in shipments:
            Move.write(shipment.moves, {'party_used': shipment.party})
        super(ShipmentExternal, cls).wait(shipments)


class ProductByPartyStart(ModelView):
    'Product by Party'
    __name__ = 'product.by_party.start'
    forecast_date = fields.Date(
        'At Date', help=('Allow to compute expected '
            'stock quantities for this date.\n'
            '* An empty value is an infinite date in the future.\n'
            '* A date in the past will provide historical values.'))

    @staticmethod
    def default_forecast_date():
        Date = Pool().get('ir.date')
        return Date.today()


class ProductByParty(Wizard):
    'Product by Party'
    __name__ = 'product.by_party'
    start = StateView('product.by_party.start',
        'stock_external.product_by_party_start_view_form', [
            Button('Cancel', 'end', 'tryton-cancel'),
            Button('Open', 'open', 'tryton-ok', default=True),
            ])
    open = StateAction('stock_external.act_party_quantity_tree')

    def do_open(self, action):
        pool = Pool()
        Product = pool.get('product.product')
        Lang = pool.get('ir.lang')

        context = {}
        product_id = Transaction().context['active_id']
        context['product'] = product_id
        if self.start.forecast_date:
            context['stock_date_end'] = self.start.forecast_date
        else:
            context['stock_date_end'] = datetime.date.max
        action['pyson_context'] = PYSONEncoder().encode(context)
        product = Product(product_id)

        for code in [Transaction().language, 'en_US']:
            langs = Lang.search([
                    ('code', '=', code),
                    ])
            if langs:
                break
        lang, = langs
        date = Lang.strftime(context['stock_date_end'],
            lang.code, lang.date)

        action['name'] += ' - %s (%s) @ %s' % (product.rec_name,
            product.default_uom.rec_name, date)
        return action, {}
