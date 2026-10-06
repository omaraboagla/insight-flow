"""Independent source workbook calculations using only Python stdlib.

Reads the original XLSX OOXML directly. It does not import or call app code.
"""
from __future__ import annotations
import json, re, zipfile
from datetime import date, timedelta
from pathlib import Path
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / 'data' / 'source'
NS = {'m':'http://schemas.openxmlformats.org/spreadsheetml/2006/main', 'r':'http://schemas.openxmlformats.org/officeDocument/2006/relationships'}
BASE = date(1899, 12, 30)
def _column_index(ref):
    n=0
    for c in re.match(r'[A-Z]+',ref).group(): n=n*26+ord(c)-64
    return n-1

def read_book(path):
    with zipfile.ZipFile(path) as z:
        ss=[]
        if 'xl/sharedStrings.xml' in z.namelist():
            root=ET.fromstring(z.read('xl/sharedStrings.xml'))
            ss=[''.join(t.text or '' for t in si.findall('.//m:t',NS)) for si in root.findall('m:si',NS)]
        book=ET.fromstring(z.read('xl/workbook.xml'))
        relroot=ET.fromstring(z.read('xl/_rels/workbook.xml.rels'))
        rel={x.attrib['Id']:x.attrib['Target'] for x in relroot}
        output=[]
        for sh in book.findall('.//m:sheet',NS):
            target=rel[sh.attrib['{'+NS['r']+'}id']].lstrip('/')
            if not target.startswith('xl/'): target='xl/'+target
            xml=ET.fromstring(z.read(target)); rows=[]
            for row in xml.findall('.//m:sheetData/m:row',NS):
                vals=[]
                for cell in row.findall('m:c',NS):
                    ix=_column_index(cell.attrib['r'])
                    while len(vals)<=ix: vals.append(None)
                    v=cell.find('m:v',NS)
                    inline=cell.find('m:is',NS)
                    x=v.text if v is not None else ''.join(t.text or '' for t in inline.findall('.//m:t',NS)) if inline is not None else None
                    if x is not None and cell.attrib.get('t')=='s': x=ss[int(x)]
                    vals[ix]=x
                rows.append(vals)
            if rows:
                header=rows[0]
                output.append([dict(zip(header,r)) for r in rows[1:] if any(v not in (None,'') for v in r)])
        return output[0] if output else []

def load():
    return {p.stem:read_book(p) for p in sorted(SOURCE.glob('*.xlsx'))}
def n(row,key): return float(row[key])
def serial_date(v): return BASE + timedelta(days=int(float(v)))
def rounded(x,d=2): return round(x,d)
def grouped(rows,key,value,transform=None,predicate=lambda r:True):
    if transform is None: transform=lambda r:r[key]
    sums={}
    for r in rows:
        if predicate(r):
            k=transform(r); sums[k]=sums.get(k,0)+value(r)
    return sorted([[k,rounded(v)] for k,v in sums.items()],key=lambda x:str(x[0]))

def calculate():
    d=load(); s=d['sales']; p=d['products']; c=d['customers']; e=d['employees']; po=d['purchases']; su=d['suppliers']
    prod={x['SKU']:x for x in p}; cust={x['CustomerID']:x for x in c}; emp={x['EmployeeID']:x for x in e}; supp={x['SupplierID']:x for x in su}
    total=lambda rows,col: rounded(sum(n(r,col) for r in rows))
    result={}
    result['g01']={'revenue':total(s,'LineTotalUSD'),'units':int(sum(n(r,'Quantity') for r in s))}
    result['g02']={'average_line_total':rounded(sum(n(r,'LineTotalUSD') for r in s)/len(s))}
    for gid,channel in [('g03','In-store'),('g04','Online')]: result[gid]={'revenue':total([r for r in s if r['Channel']==channel],'LineTotalUSD')}
    result['g05']={'rows':grouped(s, 'Channel',lambda r:n(r,'LineTotalUSD'))}
    result['g06']={'rows':grouped(s,'Category',lambda r:n(r,'LineTotalUSD'),lambda r:prod[r['SKU']]['Category'])}
    result['g07']={'rows':grouped(s,'Category',lambda r:n(r,'Quantity'),lambda r:prod[r['SKU']]['Category'])}
    result['g08']={'rows':grouped(s,'month',lambda r:n(r,'LineTotalUSD'),lambda r:serial_date(r['SaleDate']).strftime('%Y-%m'))}
    for gid,dim,join,limit in [('g09','ProductName',lambda r:prod[r['SKU']]['ProductName'],5),('g10','Customer',lambda r:cust[r['CustomerID']]['FirstName']+' '+cust[r['CustomerID']]['LastName'],5),('g11','Employee',lambda r:emp[r['SoldBy']]['FirstName']+' '+emp[r['SoldBy']]['LastName'],3)]:
        vals={}
        for r in s: vals[join(r)]=vals.get(join(r),0)+n(r,'LineTotalUSD')
        result[gid]={'rows':sorted([[k,rounded(v)] for k,v in vals.items()],key=lambda x:(-x[1],x[0]))[:limit]}
    cats={}
    for r in p: cats.setdefault(r['Category'],[]).append(n(r,'MarginPct'))
    result['g12']={'rows':[[k,rounded(sum(v)/len(v),4)] for k,v in sorted(cats.items())]}
    result['g13']={'rows':sorted([[r['ProductName'],int(n(r,'StockQty')),int(n(r,'ReorderLevel')),supp[r['SupplierID']]['SupplierName']] for r in p if n(r,'StockQty')<n(r,'ReorderLevel')])}
    pending=[r for r in po if r['Status']=='Pending']
    result['g14']={'value':total(pending,'TotalCostUSD')}; result['g15']={'rows':sorted([[r['PONumber'],rounded(n(r,'TotalCostUSD'))] for r in pending])}
    result['g16']={'rows':grouped(po,'SupplierName',lambda r:n(r,'TotalCostUSD'),lambda r:supp[r['SupplierID']]['SupplierName'])}
    vals={}
    for r in s:
        k=emp[r['SoldBy']]['FirstName']+' '+emp[r['SoldBy']]['LastName']; vals[k]=vals.get(k,0)+n(r,'LineTotalUSD')
    result['g17']={'rows':sorted([[k,rounded(v)] for k,v in vals.items()],key=lambda x:str(x[0]))}
    vals={}
    for r in s:
        k=cust[r['CustomerID']]['LoyaltyTier']; vals[k]=vals.get(k,0)+n(r,'LineTotalUSD')
    result['g18']={'rows':sorted([[k,rounded(v)] for k,v in vals.items()])}
    vals={}
    for r in s:
        k=cust[r['CustomerID']]['City']; vals[k]=vals.get(k,0)+n(r,'LineTotalUSD')
    result['g19']={'rows':sorted([[k,rounded(v)] for k,v in vals.items()])}
    vals={}
    for r in s:
        k=prod[r['SKU']]['Category']; vals[k]=vals.get(k,0)+n(r,'LineTotalUSD')
    result['g20']={'rows':sorted([[k,rounded(v)] for k,v in vals.items()],key=lambda x:(-x[1],x[0]))[:1]}
    for gid,month in [('g21','2026-01'),('g22','2026-02')]: result[gid]={'revenue':total([r for r in s if serial_date(r['SaleDate']).strftime('%Y-%m')==month],'LineTotalUSD')}
    result['g23']={'revenue':total([r for r in s if date(2026,1,1)<=serial_date(r['SaleDate'])<=date(2026,3,31)],'LineTotalUSD')}
    result['g24']={'count':sum(1 for r in s if n(r,'DiscountPct')>0)}
    result['g25']={'average_discount':rounded(sum(n(r,'DiscountPct') for r in s)/len(s),4)}
    result['g26']={'stock_units':int(sum(n(r,'StockQty') for r in p))}
    result['g27']={'rows':sorted([r['ProductName'] for r in p if supp[r['SupplierID']]['SupplierName']=='Jaipur Gem House'])}
    result['g28']={'rows':sorted([[k,sum(1 for r in c if r['LoyaltyTier']==k)] for k in {r['LoyaltyTier'] for r in c}])}
    result['g29']={'count':sum(1 for r in c if r['MarketingOptIn']=='Yes')}
    vals={}
    for r in e: vals.setdefault(r['Department'],[]).append(n(r,'AnnualSalaryUSD'))
    result['g30']={'rows':[[k,rounded(sum(v)/len(v))] for k,v in sorted(vals.items())]}
    result['g31']={'count':len(pending)}
    result['g32']={'rows':grouped(po,'Status',lambda r:n(r,'TotalCostUSD'))}
    emerald={r['SKU'] for r in p if r['Gemstone'].casefold()=='emerald'}
    result['g33']={'rows':sorted({cust[r['CustomerID']]['FirstName']+' '+cust[r['CustomerID']]['LastName'] for r in s if r['SKU'] in emerald})}
    result['g34']={'rows':grouped(s,'PaymentMethod',lambda r:n(r,'LineTotalUSD'))}
    per={}
    for r in s: per[r['CustomerID']]=per.get(r['CustomerID'],0)+n(r,'LineTotalUSD')
    result['g35']={'average_customer_spend':rounded(sum(per.values())/len(per))}
    # Follow-up pairs are independently computed from the original workbooks.
    result['f01']={'revenue':result['g23']['revenue']}  # Q1 of the dataset's 2026 sales year.
    result['f02']={'rows':sorted(result['g06']['rows'],key=lambda x:(-x[1],x[0]))}
    result['f03']={'revenue':result['g04']['revenue']}
    result['f04']={'rows':result['g09']['rows'][:3]}
    result['f05']={'rows':result['g08']['rows']}  # All source sales dates are in 2026.
    result['f06']={'rows':sorted(result['g18']['rows'],key=lambda x:(-x[1],x[0]))}
    result['f07']={'rows':result['g13']['rows']}
    active={r['EmployeeID'] for r in e if r['Status']=='Active'}
    active_totals={}
    for r in s:
        if r['SoldBy'] in active:
            k=emp[r['SoldBy']]['FirstName']+' '+emp[r['SoldBy']]['LastName']
            active_totals[k]=active_totals.get(k,0)+n(r,'LineTotalUSD')
    result['f08']={'rows':sorted([[k,rounded(v)] for k,v in active_totals.items()])}
    return result

if __name__=='__main__':
    target=ROOT/'tests/golden/expected_results.json'
    target.write_text(json.dumps(calculate(),indent=2,ensure_ascii=False)+'\n')
    print(f'Wrote independently calculated answers to {target.relative_to(ROOT)}')
