# The COPYRIGHT file at the top level of this repository contains the full
# copyright notices and license terms.
from trytond.pool import Pool
from . import product
from . import stock


def register():
    Pool.register(
        stock.Party,
        product.Template,
        product.TemplateOwnerParty,
        product.Product,
        product.ProductByPartyStart,
        stock.Location,
        stock.Move,
        stock.ShipmentOut,
        stock.ShipmentExternal,
        stock.Period,
        stock.PeriodCacheParty,
        stock.Inventory,
        stock.InventoryLine,
        module='stock_external_party', type_='model')
    Pool.register(
        product.ProductByParty,
        module='stock_external_party', type_='wizard')
    Pool.register(
        stock.Lot,
        depends=['stock_lot'],
        module='stock_external_party', type_='model')
