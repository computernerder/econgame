import copy
import json
import re
from html.parser import HTMLParser

from markupsafe import Markup
from test_game import game
from test_business import acquire
from test_campaign_product import client_for
from economic_simulation.money_display import money, whole_money_text, display_payload
from economic_simulation.campaign_views import PAGES
from economic_simulation.web import DisplayJSONResponse


class Visible(HTMLParser):
    def __init__(self):
        super().__init__(); self.text=[]; self.inputs=[]
    def handle_data(self, data): self.text.append(data)
    def handle_starttag(self, tag, attrs):
        if tag=='input': self.inputs.append(dict(attrs))


def test_rounding_and_non_money_precision():
    cases={0:'$0',49:'$0',50:'$1',149:'$1',150:'$2',-49:'$0',-50:'−$1',-150:'−$2',123456789:'$1,234,568'}
    for cents, expected in cases.items(): assert money(cents)==expected
    assert whole_money_text('Cost $1,234.56; refund −$12.50; 2.75 hours; 1.25%')=='Cost $1,235; refund −$13; 2.75 hours; 1.25%'
    assert isinstance(whole_money_text(Markup('<b>$12.50</b>')), Markup)
    assert not isinstance(whole_money_text('<b>$12.50</b>'), Markup)


def test_json_presentation_keeps_numeric_cents_and_source_history():
    source={'message':'Paid $12.34', 'cash':1234, 'items':[{'detail':'Owed $-10.50'}]}
    before=copy.deepcopy(source)
    result=json.loads(DisplayJSONResponse(source).body)
    assert result=={'message':'Paid $12', 'cash':1234, 'items':[{'detail':'Owed −$11'}]}
    assert source==before
    assert display_payload({'rate':1.25})=={'rate':1.25}


def test_pages_show_whole_dollars_without_mutating_saved_amounts(game):
    bid=acquire(game)
    employee=next(e for e in game.world.employments if e.employer==bid)
    employee.salary=345678
    before=copy.deepcopy(game.world.to_dict())
    client=client_for(game)
    pages=[{'page':p,'scope':bid} for p in sorted(PAGES)]
    pages += [{'page':p,'scope':bid,'business_id':bid,'employment_id':employee.id,'property_id':game.world.properties[0].id} for p in ('overview','market','portfolio','property','finance','owner','activity','business_market','businesses','business','people','employee','organization','management','games')]
    for params in pages:
        response=client.get('/',params=params)
        assert response.status_code==200, params
        visible=Visible();visible.feed(response.text)
        assert not re.search(r'\$[−-]?\d[\d,]*\.\d+', ' '.join(visible.text)), params
        for field in visible.inputs:
            if field.get('name','').endswith('_dollars') and field.get('type')=='number':
                assert field.get('step')=='1', (params,field)
                if field.get('value'): assert re.fullmatch(r'-?\d+',field['value']), (params,field)
    html=client.get('/?page=employee&employment_id='+employee.id).text
    assert 'value="3457" data-exact-dollars="3456.78"' in html
    assert game.world.to_dict()==before
