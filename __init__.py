# The COPYRIGHT file at the top level of this repository contains the full
# copyright notices and license terms.
from trytond.pool import Pool
from .product import *
from .stock import *


def register():
    Pool.register(
        Party,
        Template,
        TemplateOwnerParty,
        Product,
        ProductByPartyStart,
        Location,
        Move,
        ShipmentOut,
        ShipmentExternal,
        Period,
        PeriodCacheParty,
        Inventory,
        InventoryLine,
        module='stock_external_party', type_='model')
    Pool.register(
        ProductByParty,
        module='stock_external_party', type_='wizard')
