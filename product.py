# The COPYRIGHT file at the top level of this repository contains the full
# copyright notices and license terms.
import datetime

from trytond.model import fields, ModelSQL, ModelView
from trytond.pool import Pool, PoolMeta
from trytond.pyson import Eval, PYSONEncoder
from trytond.transaction import Transaction
from trytond.wizard import Wizard, StateView, StateAction, Button

__all__ = ['Template', 'TemplateOwnerParty',
    'Product', 'ProductByPartyStart', 'ProductByParty',
    ]


class Template(metaclass=PoolMeta):
    __name__ = 'product.template'

    may_belong_to_party = fields.Boolean('May belong to party', states={
            'readonly': ~Eval('active', True),
            }, depends=['active'])
    external_owners = fields.Many2Many('product.template-owner-party.party',
        'product', 'party', 'External Owners', states={
            'readonly': ~Eval('active', True),
            'invisible': ~Eval('may_belong_to_party', False),
            }, depends=['active', 'may_belong_to_party'])


class TemplateOwnerParty(ModelSQL):
    'Template - Owner - Party'
    __name__ = 'product.template-owner-party.party'
    product = fields.Many2One('product.template', 'Product',
        ondelete='CASCADE', required=True, select=True)
    party = fields.Many2One('party.party', 'Owner', ondelete='CASCADE',
        required=True, select=True)


class Product(metaclass=PoolMeta):
    __name__ = 'product.product'

    @classmethod
    def get_cost_value(cls, products, name):
        with Transaction().set_context(exclude_party_quantities=True):
            return super(Product, cls).get_cost_value(products, name)


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
