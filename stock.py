# The COPYRIGHT file at the top level of this repository contains the full
# copyright notices and license terms.
import datetime
from collections import defaultdict
from trytond.model import ModelSQL, ModelView, fields
from trytond.pool import Pool, PoolMeta
from trytond.pyson import PYSONEncoder
from trytond.transaction import Transaction
from trytond.wizard import Wizard, StateView, StateAction, Button
from trytond.modules.stock.move import STATES, DEPENDS
from trytond.modules.stock import StockMixin

__all__ = ['Party', 'Product', 'Location',
    'Move', 'ShipmentOut', 'ShipmentExternal',
    'ProductByPartyStart', 'ProductByParty',
    'Period', 'PeriodCacheParty',
    'Inventory', 'InventoryLine']
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
        Location = pool.get('stock.location')
        transaction = Transaction()
        context = transaction.context
        location_ids = context.get('locations')
        if not location_ids:
            warehouses = Location.search([
                    ('type', '=', 'warehouse')
                    ])
            location_ids = [x.id for x in warehouses]
        products = None
        if context.get('products'):
            products = Product.browse(context.get('products'))
        pbl = cls._get_quantity(parties, name, list(location_ids), products,
            grouping=('product', 'party'))
        return pbl

    @classmethod
    def search_quantity(cls, name, domain=None):
        location_ids = Transaction().context.get('locations')
        return cls._search_quantity(name, location_ids, domain,
            grouping=('product', 'party_used'))


class Product:
    __name__ = 'product.product'

    @classmethod
    def get_cost_value(cls, products, name):
        with Transaction().set_context(exclude_party_quantities=True):
            return super(Product, cls).get_cost_value(products, name)


class Location:
    __name__ = 'stock.location'

    @classmethod
    def get_cost_value(cls, locations, name):
        with Transaction().set_context(exclude_party_quantities=True):
            return super(Location, cls).get_cost_value(locations, name)


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
        if (self.party_used and (self.to_location.type in types_to_check or
                    wh_output and self.to_location == wh_output)
                and self.party_used != self.party_to_check):
            self.raise_user_error('diferent_party', (self.rec_name,
                    self.party_used.rec_name,
                    self.party_to_check.rec_name
                        if self.party_to_check else 'none'))

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
                new_grouping_filter = grouping_filter[:] + (None, )

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
                new_grouping_filter = grouping_filter[:] + (None, )
            remove_party_grouping = True

        quantities = super(Move, cls).compute_quantities(query, location_ids,
            with_childs=with_childs, grouping=new_grouping,
            grouping_filter=new_grouping_filter)

        if remove_party_grouping:
            new_quantities = {}
            for key, quantity in quantities.iteritems():
                if key[-1] is not None:
                    # party quantity. ignore
                    continue
                parent_key = ()
                for key_item in key[:-2]:
                    parent_key = parent_key + (key_item, )
                    new_quantities.setdefault(parent_key, {})
                new_quantities[key[:-1]] = quantity
            quantities = new_quantities
        return quantities


class ShipmentOut:
    __name__ = 'stock.shipment.out'

    def _get_inventory_move(self, move):
        inv_move = super(ShipmentOut, self)._get_inventory_move(move)
        if move.party:
            inv_move.party = move.party
        return inv_move


class ShipmentExternal:
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
        'stock_external_party.product_by_party_start_view_form', [
            Button('Cancel', 'end', 'tryton-cancel'),
            Button('Open', 'open', 'tryton-ok', default=True),
            ])
    open = StateAction('stock_external_party.act_party_quantity_tree')

    def do_open(self, action):
        pool = Pool()
        Product = pool.get('product.product')
        Lang = pool.get('ir.lang')

        context = {}
        product_id = Transaction().context['active_id']
        context['products'] = [product_id]
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


class Period:
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


class Inventory:
    __name__ = 'stock.inventory'

    @staticmethod
    def grouping():
        return ('product', 'party')

    @classmethod
    def complete_lines(cls, inventories):
        pool = Pool()
        Product = pool.get('product.product')
        Line = pool.get('stock.inventory.line')

        super(Inventory, cls).complete_lines(inventories)

        grouping = cls.grouping()

        def get_subkey(line):
            subkey = []
            for fname in grouping[1:]:
                fvalue = getattr(line, fname, None)
                if fvalue:
                    fvalue = fvalue.id
                subkey.append(fvalue)
            return tuple(subkey)

        # Create and/or update lines with product that are from a party.
        to_create = []
        to_write = []
        for inventory in inventories:
            product2lines = defaultdict(list)
            for line in inventory.lines:
                product2lines[line.product.id].append(line)
            if product2lines:
                with Transaction().set_context(stock_date_end=inventory.date):
                    pbl = Product.products_by_location([inventory.location.id],
                        product_ids=product2lines.keys(),
                        grouping=grouping)
                product_qty = defaultdict(dict)
                for key, quantity in pbl.iteritems():
                    product_id = key[1]
                    subkey = key[2:]
                    product_qty[product_id][subkey] = quantity

                products = Product.browse(product_qty.keys())
                product2uom = dict((p.id, p.default_uom.id) for p in products)

                for product_id, lines in product2lines.iteritems():
                    quantities = product_qty[product_id]
                    uom_id = product2uom[product_id]
                    for line in lines:
                        subkey = get_subkey(line)
                        force_update = False
                        if subkey in quantities:
                            quantity = quantities.pop(subkey)
                        elif all(k is None for k in subkey) and quantities:
                            subkey = quantities.keys()[0]
                            quantity = quantities.pop(subkey)
                            force_update = True
                        else:
                            quantity = 0.0
                            force_update = True

                        values = line.update_values4complete(quantity, uom_id)
                        if (values or force_update):
                            for i, fname in enumerate(grouping[1:]):
                                values[fname] = subkey[i]
                            to_write.extend(([line], values))
                    if quantities:
                        for subkey, quantity in quantities.iteritems():
                            values = Line.create_values4complete(product_id,
                                inventory, quantity, uom_id)
                            for i, fname in enumerate(grouping[1:]):
                                values[fname] = subkey[i]
                            to_create.append(values)
        if to_create:
            Line.create(to_create)
        if to_write:
            Line.write(*to_write)


class InventoryLine:
    __name__ = 'stock.inventory.line'
    party = fields.Many2One('party.party', 'Party')

    def get_rec_name(self, name):
        rec_name = super(InventoryLine, self).get_rec_name(name)
        if self.party:
            rec_name += ' - %s' % self.party.rec_name
        return rec_name

    @property
    def unique_key(self):
        return super(InventoryLine, self).unique_key + (self.party,)

    def get_move(self):
        move = super(InventoryLine, self).get_move()
        if move:
            if self.party:
                move.party_used = self.party
        return move
