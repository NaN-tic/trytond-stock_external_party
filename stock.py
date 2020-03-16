# The COPYRIGHT file at the top level of this repository contains the full
# copyright notices and license terms.
from trytond.model import ModelSQL, ModelView, fields
from trytond.pool import Pool, PoolMeta
from trytond.transaction import Transaction
from trytond.modules.stock.move import STATES, DEPENDS
from trytond.modules.stock import StockMixin
from trytond.i18n import gettext
from trytond.exceptions import UserError


__all__ = ['Party', 'Location',
    'Move', 'ShipmentOut', 'ShipmentExternal',
    'Period', 'PeriodCacheParty',
    'Inventory', 'InventoryLine']


class Party(StockMixin, metaclass=PoolMeta):
    __name__ = 'party.party'
    quantity = fields.Function(fields.Float('Quantity'), 'get_quantity',
        searcher='search_quantity')
    forecast_quantity = fields.Function(fields.Float('Forecast Quantity'),
        'get_quantity', searcher='search_quantity')

    @classmethod
    def get_quantity(cls, parties, name):
        pool = Pool()
        Product = pool.get('product.product')
        Location = pool.get('stock.location')
        transaction = Transaction()
        context = transaction.context
        location_ids = context.get('locations')
        if not location_ids:
            warehouses = Location.search([
                    ('type', '=', 'warehouse')
                    ])
            location_ids = [x.id for x in warehouses]
        product_ids = None
        if context.get('products'):
            product_ids =[x.id for x in Product.browse(context.get('products'))]

        pbl = cls._get_quantity(parties, name, list(location_ids),
            grouping=('product', 'party',), grouping_filter=(product_ids,))
        return pbl

    @classmethod
    def search_quantity(cls, name, domain=None):
        location_ids = Transaction().context.get('locations')
        return cls._search_quantity(name, location_ids, domain,
            grouping=('product', 'party_used'))


class Location(metaclass=PoolMeta):
    __name__ = 'stock.location'

    @classmethod
    def get_cost_value(cls, locations, name):
        with Transaction().set_context(exclude_party_quantities=True):
            return super(Location, cls).get_cost_value(locations, name)

    @classmethod
    def _quantity_grouping_and_key(cls):
        grouping, key = super(Location, cls)._quantity_grouping_and_key()

        party_id = Transaction().context.get('party')
        if party_id:
            grouping = grouping + ('party',)
            key = key + (party_id,)
        return grouping, key


class Move(metaclass=PoolMeta):
    __name__ = 'stock.move'
    party = fields.Many2One('party.party', 'Party')
    party_used = fields.Function(fields.Many2One('party.party', 'Party',
            states=STATES, depends=DEPENDS),
        'on_change_with_party_used', setter='set_party_used',
            searcher='search_party_used')
    party_to_check = fields.Function(fields.Many2One('party.party', 'Party'),
        'get_party_to_check')


    @fields.depends('party')
    def on_change_with_party_used(self, name=None):
        if self.party:
            return self.party.id

    @classmethod
    def set_party_used(cls, moves, name, value):
        cls.write(moves, {'party': value})

    @classmethod
    def search_party_used(cls, name, clause):
        return [('party',) + tuple(clause[1:])]

    def get_party_to_check(self, name):
        '''
        Returns the party to check if it\'s the same as the party used in
        the move when making the move.

        By default it returns the party of the shipment of the move.
        If no shipment an error is raised.
        '''
        if not self.shipment:
            raise UserError(gettext(
                'stock_external_party.required_shipment',
                move=self.rec_name))
        for name in ('customer', 'supplier', 'party'):
            if hasattr(self.shipment, name):
                return getattr(self.shipment, name).id

    @classmethod
    def location_types_to_check_party(cls):
        '''
        Returns a list of to locations types that must be checked before
        allowing a move with party defined to be done
        '''
        return ['customer', 'supplier']

    @classmethod
    def assign_try(cls, moves, with_childs=True, grouping=('product',)):
        for move in moves:
            move._check_party()
        if 'party' not in grouping:
            grouping = grouping + ('party',)
        return super(Move, cls).assign_try(moves, with_childs=with_childs,
            grouping=grouping)

    @classmethod
    def do(cls, moves):
        for move in moves:
            move._check_party()
        super(Move, cls).do(moves)

    def _check_party(self):
        types_to_check = self.location_types_to_check_party()
        wh_output = (getattr(self.shipment, 'warehouse_output', None)
            if self.shipment else None)
        if not (self.to_location.type in types_to_check
                or wh_output and self.to_location == wh_output):
            return
        if (self.party_used and self.party_to_check
                and self.party_used != self.party_to_check):
            raise UserError(gettext('stock_external_party.diferent_party',
                move=self.rec_name,
                party=self.party_used.rec_name,
                send_party=(self.party_to_check.rec_name if self.party_to_check
                    else 'none')))

    @classmethod
    def compute_quantities_query(cls, location_ids, with_childs=False,
            grouping=('product',), grouping_filter=None):
        context = Transaction().context

        new_grouping = grouping[:]
        new_grouping_filter = (grouping_filter[:]
            if grouping_filter is not None else None)
        if 'party' not in grouping and context.get('exclude_party_quantities'):
            new_grouping = grouping[:] + ('party',)
            if grouping_filter is not None:
                new_grouping_filter = grouping_filter[:]

        query = super(Move, cls).compute_quantities_query(
            location_ids, with_childs=with_childs, grouping=new_grouping,
            grouping_filter=new_grouping_filter)
        return query

    @classmethod
    def compute_quantities(cls, query, location_ids, with_childs=False,
            grouping=('product',), grouping_filter=None):

        context = Transaction().context

        new_grouping = grouping[:]
        new_grouping_filter = (grouping_filter[:]
            if grouping_filter is not None else None)
        remove_party_grouping = False
        if 'party' not in grouping and context.get('exclude_party_quantities'):
            new_grouping = grouping[:] + ('party',)
            if grouping_filter is not None:
                new_grouping_filter = grouping_filter[:]
            remove_party_grouping = True

        quantities = super(Move, cls).compute_quantities(query, location_ids,
            with_childs=with_childs, grouping=new_grouping,
            grouping_filter=new_grouping_filter)

        if remove_party_grouping:
            new_quantities = {}
            for key, quantity in quantities.items():
                new_quantities.setdefault(key[:-1], 0.)
                if key[-1] is not None:
                    # party quantity. ignore
                    continue
                new_quantities[key[:-1]] += quantity
            quantities = new_quantities
        return quantities


class ShipmentOut(metaclass=PoolMeta):
    __name__ = 'stock.shipment.out'

    def _get_inventory_move(self, move):
        inv_move = super(ShipmentOut, self)._get_inventory_move(move)
        if move.party:
            inv_move.party = move.party
        return inv_move


class ShipmentExternal(metaclass=PoolMeta):
    __name__ = 'stock.shipment.external'

    @classmethod
    def draft(cls, shipments):
        pool = Pool()
        Move = pool.get('stock.move')
        moves = list(m for s in shipments for m in s.moves)
        Move.write(moves, {'party_used': None})
        super(ShipmentExternal, cls).draft(shipments)

    @classmethod
    def wait(cls, shipments):
        pool = Pool()
        Move = pool.get('stock.move')
        for shipment in shipments:
            Move.write(list(shipment.moves), {'party_used': shipment.party})
        super(ShipmentExternal, cls).wait(shipments)


class Period(metaclass=PoolMeta):
    __name__ = 'stock.period'
    party_caches = fields.One2Many('stock.period.cache.party', 'period',
        'Party Caches', readonly=True)

    @classmethod
    def groupings(cls):
        return super(Period, cls).groupings() + [('product', 'party')]

    @classmethod
    def get_cache(cls, grouping):
        pool = Pool()
        Cache = super(Period, cls).get_cache(grouping)
        if grouping == ('product', 'party'):
            return pool.get('stock.period.cache.party')
        return Cache


class PeriodCacheParty(ModelSQL, ModelView):
    '''
    Stock Period Cache per Party

    It is used to store cached computation of stock quantities per party.
    '''
    __name__ = 'stock.period.cache.party'
    period = fields.Many2One('stock.period', 'Period', required=True,
        readonly=True, select=True, ondelete='CASCADE')
    location = fields.Many2One('stock.location', 'Location', required=True,
        readonly=True, select=True, ondelete='CASCADE')
    product = fields.Many2One('product.product', 'Product', required=True,
        readonly=True, ondelete='CASCADE')
    party = fields.Many2One('party.party', 'Party', readonly=True,
        ondelete='CASCADE')
    internal_quantity = fields.Float('Internal Quantity', readonly=True)


class Inventory(metaclass=PoolMeta):
    __name__ = 'stock.inventory'

    @classmethod
    def grouping(cls):
        return super(Inventory, cls).grouping() + ('party', )


class InventoryLine(metaclass=PoolMeta):
    __name__ = 'stock.inventory.line'
    party = fields.Many2One('party.party', 'Party')

    def get_rec_name(self, name):
        rec_name = super(InventoryLine, self).get_rec_name(name)
        if self.party:
            rec_name += ' - %s' % self.party.rec_name
        return rec_name

    def get_move(self):
        move = super(InventoryLine, self).get_move()
        if move:
            if self.party:
                move.party_used = self.party
        return move
