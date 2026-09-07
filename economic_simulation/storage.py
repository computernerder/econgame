"""Finite storage units, monthly tenants and daily rental collections."""
from .domain import daily_share


def operate_storage(rules,b,today,minutes,open_day):
    operating=b.status in ('operating','independent')
    moved_out=moved_in=0
    # Existing tenants keep access and pay rent outside staffed office hours.
    if operating and today.day==1 and b.storage_occupied:
        moved_out=max(1,b.storage_occupied//40)
        b.storage_occupied-=moved_out
    if open_day:
        from .economy import Economy
        target=min(b.storage_units*95//100,b.storage_units*Economy(rules.e).demand_factor(b)//125)
        moved_in=min(max(0,target-b.storage_occupied),3,minutes.get('property_manager',0)//30)
        b.storage_occupied+=moved_in
        shortage=max(0,b.storage_units*2-minutes.get('maintenance',0))
        if shortage:
            cost=shortage*60
            rules.e.post(b.id,f'storage-maintenance:{b.id}:{rules.w.date}','Outsourced storage upkeep',{'expense:outsourced_maintenance':cost,'liability:payable':-cost})
    rent=b.storage_occupied*daily_share(b.storage_monthly_rent,today) if operating else 0
    if rent:
        rules.e.post(b.id,f'storage-rent:{b.id}:{rules.w.date}','Rent collected from storage tenants',{'asset:cash':rent,'income:storage_rent':-rent})
    return dict(output=b.storage_occupied,unit='occupied storage units',demand=b.storage_units,
                moved_in=moved_in,moved_out=moved_out,storage_rent=rent,
                bottleneck='Opening preparations' if not operating else 'Fully occupied' if b.storage_occupied==b.storage_units else 'Office closed; existing tenants continue paying rent' if not open_day else 'Property-manager hours' if minutes.get('property_manager',0)<30 else 'Regional demand and tenant turnover')
