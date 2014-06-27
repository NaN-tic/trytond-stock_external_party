# The COPYRIGHT file at the top level of this repository contains the full
# copyright notices and license terms.
from trytond.pool import Pool
from .stock import *


def register():
    Pool.register(
        Party,
        Move,
        ShipmentExternal,
        ProductByPartyStart,
        Period,
        PeriodCacheParty,
        Inventory,
        InventoryLine,
        module='stock_external', type_='model')
    Pool.register(
        ProductByParty,
        module='stock_external', type_='wizard')
