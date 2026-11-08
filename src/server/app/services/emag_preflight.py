"""Bounded in-memory XLSX inspection, with no platform-ready attestation."""
from io import BytesIO
from pathlib import PurePosixPath
import re
from xml.etree import ElementTree
from zipfile import ZipFile, BadZipFile
from openpyxl import load_workbook
from openpyxl.utils import get_column_letter, column_index_from_string
from app.services import emag_commerce as commerce, store_artifacts as artifacts

MAX_BYTES=5*1024*1024
GUIDANCE=re.compile(r'training|guidance|instruction|example|sample|教程|说明|示例|填写指引|填写指导',re.I)
REQUIRED=re.compile(r'^(?:required|mandatory|obligatoriu|obligatorie|必填)(?:\b|\s|$)',re.I)
FIELD=re.compile(r'^[a-z][a-z0-9_]*(?:\[[^\]]+\])?$')


def _archive(content):
    unexamined=False
    try:
        with ZipFile(BytesIO(content)) as archive:
            infos=archive.infolist()
            if len(infos)>500 or sum(i.file_size for i in infos)>64*1024*1024:raise ValueError('XLSX expanded ZIP limit exceeded')
            for item in infos:
                path=PurePosixPath(item.filename)
                if path.is_absolute() or '..' in path.parts or '\\' in item.filename:raise ValueError('Unsafe ZIP path')
                name=item.filename.lower()
                if item.flag_bits&1 or 'vba' in name or 'activex' in name or 'externallinks' in name or name.endswith('.bin'):raise ValueError('Unsupported active XLSX content')
                if name.endswith(('.xml','.rels')):
                    raw=archive.read(item)
                    if b'\x00' in raw or b'<!DOCTYPE' in raw.upper() or b'<!ENTITY' in raw.upper():raise ValueError('DTD and entities are unsupported')
                    if re.search(br"targetmode\s*=\s*[\"']external",raw,re.I):raise ValueError('External XLSX relationships are unsupported')
                    if b'macroenabled' in raw.lower():raise ValueError('Macro-enabled workbooks are unsupported')
                    try:tree=ElementTree.fromstring(raw)
                    except ElementTree.ParseError as exc:raise ValueError('Invalid XLSX XML') from exc
                    if tree.tag=='{http://schemas.openxmlformats.org/spreadsheetml/2006/main}worksheet':
                        # Inspect actual XML cells, never the optional/forgeable dimension hint.
                        for cell in tree.iter('{http://schemas.openxmlformats.org/spreadsheetml/2006/main}c'):
                            match=re.fullmatch(r'([A-Z]{1,3})([1-9][0-9]{0,6})',cell.get('r',''))
                            if not match:unexamined=True;continue
                            if int(match[2])>1006 or column_index_from_string(match[1])>300:unexamined=True
    except BadZipFile as exc:raise ValueError('Invalid XLSX ZIP') from exc
    return unexamined


def check(store_id,snapshot_id,file_name,content):
    if len(content)>MAX_BYTES:raise OverflowError('Upload exceeds 5 MiB')
    if not isinstance(file_name,str) or not file_name.lower().endswith('.xlsx'):raise ValueError('An XLSX file is required')
    file_name=file_name.replace('\\','/').rsplit('/',1)[-1][:200]
    with artifacts.snapshot_guard():
        snapshot=commerce.source(store_id)
        if snapshot['snapshot_id']!=snapshot_id:raise ValueError('Evidence is stale; reload first')
        unexamined=_archive(content)
        try:book=load_workbook(BytesIO(content),read_only=True,data_only=False,keep_links=False)
        except Exception as exc:raise ValueError('Unreadable XLSX workbook') from exc
        result={'store_id':store_id,'snapshot_id':snapshot_id,'file_name':file_name,'status':'unsupported',
                'layout':{'sheet':None,'header_row':None,'data_start_row':None,'fields':[]},'row_count':0,
                'issues':[],'truncated':False,'knowledge_query':'模板','marketplace_writes':False}
        def issue(code,sheet=None,row=None,column=None,field=None,details='Manual review required.'):
            if len(result['issues'])<200:result['issues'].append({'code':code,'severity':'review','sheet':sheet,'row':row,'column':column,'field':field,'details':details})
            else:result['truncated']=True
        try:
            if unexamined:
                result['truncated']=True
                issue('unexamined_cells',details='Workbook XML contains cells outside physical rows 1–1006 / columns 1–300, or cells with unknown coordinates. Those cells were not examined.')
            if GUIDANCE.search(file_name):issue('guidance_only');return result
            candidates=[]
            for sheet in book.worksheets:
                # Ignore misleading dimension metadata; never iterate arbitrary declared dimensions.
                sheet.reset_dimensions()
                head=list(sheet.iter_rows(min_row=1,max_row=5,max_col=300,values_only=True))
                for index,row in enumerate(head):
                    fields=[str(v).strip() if v is not None else '' for v in row]
                    if {'part_number','ext_id','category_id','sale_price'}<=set(fields):candidates.append((sheet,index+1,fields,head))
            if len(candidates)!=1:issue('unsupported_or_ambiguous_layout');return result
            sheet,header,fields,head=candidates[0]
            nonempty=[f for f in fields if f]
            if header!=3 or len(nonempty)!=len(set(nonempty)) or any(not FIELD.fullmatch(f) for f in nonempty):issue('unsupported_or_ambiguous_layout',sheet.title);return result
            result['layout']={'sheet':sheet.title,'header_row':header,'data_start_row':6,'fields':nonempty}
            result['status']='needs_review'
            required={i for i,f in enumerate(fields) if f and REQUIRED.search(str(head[3][i] or '').strip())}
            if not required:issue('required_fields_unknown',sheet.title)
            identities={};families={}
            for row_number,row in enumerate(sheet.iter_rows(min_row=6,max_row=1006,max_col=len(fields)),6):
                if not any(c.value is not None for c in row):continue
                if result['row_count']>=1000:result['truncated']=True;issue('row_limit',sheet.title,row_number);break
                result['row_count']+=1
                values={fields[i]:cell.value for i,cell in enumerate(row) if fields[i]}
                if any(isinstance(v,str) and (GUIDANCE.search(v) or row_number in (6,7) and re.search(r'请填|请确保|必须|总是|比如|填写',v)) for v in values.values()):issue('template_guidance_row',sheet.title,row_number)
                for i,cell in enumerate(row):
                    field=fields[i]
                    if not field:continue
                    column=get_column_letter(i+1)
                    if cell.data_type=='f':issue('formula_requires_review',sheet.title,row_number,column,field)
                    if i in required and (cell.value is None or isinstance(cell.value,str) and not cell.value.strip()):issue('required_blank',sheet.title,row_number,column,field)
                    if field in ('part_number','ext_id') and cell.value is not None:
                        key=(field,str(cell.value).strip())
                        if key in identities:issue('duplicate_identity',sheet.title,row_number,column,field,f'Duplicate of row {identities[key]}.')
                        else:identities[key]=row_number
                family=values.get('family_id')
                if family not in (None,''):
                    metadata={k:v for k,v in values.items() if k.startswith('family_') and k!='family_id'}
                    if family in families and families[family]!=metadata:issue('family_metadata_mismatch',sheet.title,row_number,field='family_id')
                    else:families[family]=metadata
            if not result['row_count']:issue('no_product_rows',sheet.title,details='No product rows were examined; an empty template is not a completed product file.')
            issue('platform_rules_not_verified',sheet.title,details='Local structural checks only; verify current category requirements, product evidence and platform validation. Training or sample rows require manual review.')
            return result
        finally:book.close()
