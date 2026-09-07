"""Legal and purchasing products reuse staffed service delivery."""
from .campaign import Campaign
from .domain import RuleError

PRODUCTS={
    'transaction_review':('legal','Review property transaction terms',720),
    'transfer_consent':('legal','Obtain property transfer consent',1200),
    'supplier_tender':('purchasing','Obtain outside-service supplier quotes',720),
}


class CommercialWork(Campaign):
    def prepare(self,task,args):
        product=args.get('product','')
        if product not in PRODUCTS:return False
        if task['department']!=PRODUCTS[product][0]:raise RuleError('Select the correct department for this work product.')
        task.update(product=product,effort=PRODUCTS[product][2],remaining=PRODUCTS[product][2])
        if product=='supplier_tender':
            from .service_office import DEPARTMENTS
            department=args.get('service_department','legal')
            if department not in DEPARTMENTS:raise RuleError('Select a service department for the supplier agreement.')
            task['service_department']=department
        else:
            from .transaction_legal import TransactionLegal
            TransactionLegal(self.e).prepare(task)
        return True

    def finish(self,task,quality):
        if task.get('product') not in PRODUCTS:return False
        if task['product']=='supplier_tender':
            from .supplier_contracts import SupplierContracts
            SupplierContracts(self.e).offers(task,quality)
        else:
            from .transaction_legal import TransactionLegal
            TransactionLegal(self.e).finish(task,quality)
        return True
