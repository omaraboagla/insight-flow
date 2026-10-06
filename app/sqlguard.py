"""AST validation before every SQL execution; no file/network capability."""
import re
import sqlglot
from sqlglot import exp
from sqlglot.optimizer.qualify import qualify
from sqlglot.errors import OptimizeError

class SQLValidationError(ValueError): pass

DENIED_NAMES={'copy','attach','detach','install','load','pragma','set','export','import','call','execute','query','query_table','glob','httpfs','getenv','read_blob','read_text','write_file','sqlite_scan','postgres_scan','mysql_scan','delta_scan','iceberg_scan','parquet_scan','csv_scan','json_scan','range','generate_series'}
ALLOWED_ANONYMOUS={'strftime','strptime','try_strptime','date_trunc','date_part','date_diff','datediff','round','ifnull','isfinite','regexp_matches','regexp_replace','regexp_extract','string_agg','median','quantile_cont','quantile_disc','count_if','arg_max','arg_min','first','last','list','list_agg','unaccent','format','printf','year','month','day','quarter','week','make_date','typeof'}

def validate_sql(sql, tables, relationships=None):
    if not isinstance(sql,str) or not sql.strip(): raise SQLValidationError('The query is empty.')
    try: statements=sqlglot.parse(sql,read='duckdb')
    except Exception: raise SQLValidationError('The SQL could not be parsed.') from None
    if len(statements)!=1 or not isinstance(statements[0],(exp.Select,exp.Union)):
        raise SQLValidationError('Only one SELECT statement is allowed.')
    tree=statements[0]
    prohibited=(exp.Insert,exp.Update,exp.Delete,exp.Create,exp.Drop,exp.Command,exp.Into,exp.Merge,exp.Alter)
    for node in tree.walk():
        if isinstance(node,prohibited): raise SQLValidationError('Data modification and commands are forbidden.')
        if isinstance(node,exp.Func):
            fname=node.name.lower() if isinstance(node,exp.Anonymous) else node.sql_name().lower()
            if fname.startswith(('read_','write_','http','sqlite','postgres','mysql','duckdb_','current_setting','system','shell','eval')) or fname in DENIED_NAMES:
                raise SQLValidationError('File, network, and system functions are forbidden.')
            if isinstance(node,exp.Anonymous) and fname not in ALLOWED_ANONYMOUS:
                raise SQLValidationError(f'Unsupported function: {fname}.')
    ctes={cte.alias_or_name.lower() for cte in tree.find_all(exp.CTE)}
    referenced=[]
    for t in tree.find_all(exp.Table):
        if not isinstance(t.this,exp.Identifier) or t.catalog or t.db:
            raise SQLValidationError('Only loaded local tables are allowed.')
        name=t.name.lower()
        if name not in tables and name not in ctes: raise SQLValidationError(f'Unknown table: {name}.')
        if name in tables: referenced.append(name)
    schema={name:{c['name']:('TIMESTAMP' if c['type']=='date' else 'DOUBLE' if c['type'] in ('number','currency','percent') else 'BOOLEAN' if c['type']=='boolean' else 'VARCHAR') for c in t.columns} for name,t in tables.items()}
    try:
        qualified=qualify(tree.copy(),dialect='duckdb',schema=schema,validate_qualify_columns=True,identify=True)
    except Exception as exc: raise SQLValidationError('A column does not exist or is ambiguous. Qualify columns with their table aliases.') from None
    _joined_relationships(qualified,tables,relationships or [],require=bool(list(qualified.find_all(exp.Join))))
    limit=tree.args.get('limit')
    if limit is None: tree=tree.limit(1000)
    else:
        value=limit.expression
        if not isinstance(value,exp.Literal) or not value.is_int or int(value.this)<0: raise SQLValidationError('LIMIT must be a non-negative integer.')
        if int(value.this)>1000: tree=tree.limit(1000)
    return tree.sql(dialect='duckdb')

def _relationship_pair(relation):
    return frozenset(((relation['from_table'].lower(),relation['from_column'].lower()),
                      (relation['to_table'].lower(),relation['to_column'].lower())))

def _joined_relationships(tree,tables,relationships,require=True):
    """Return only relationships enforced by safe ON predicates.

    Every physical JOIN target must participate in a detected key equality to a
    table already in that SELECT's FROM/JOIN scope. OR and NOT are prohibited in
    ON because they can make a key equality optional (for example, ``key OR 1=1``).
    """
    used=[]
    approved={_relationship_pair(r):r for r in relationships}
    ctes={cte.alias_or_name.lower() for cte in tree.find_all(exp.CTE)}
    selects=list(tree.find_all(exp.Select)) or ([tree] if isinstance(tree,exp.Select) else [])
    for select in selects:
        source=select.args.get('from_')
        if source is None: continue
        base=source.this
        extra=source.args.get('expressions') or []
        if extra:
            raise SQLValidationError('Comma-separated tables are not a safe JOIN. Use a detected explicit relationship.')
        scope={}
        if isinstance(base,exp.Table):
            name=base.name.lower()
            if name in tables: scope[base.alias_or_name.lower()]=name
            elif name not in ctes: raise SQLValidationError('Only loaded local tables can be joined.')
        elif isinstance(base,exp.Subquery):
            # A derived table has no trusted relationship lineage to another table.
            scope[base.alias_or_name.lower()]=''
        for join in select.args.get('joins') or []:
            target=join.this
            if not isinstance(target,exp.Table):
                raise SQLValidationError('JOIN targets must be loaded tables with detected relationship keys.')
            target_name=target.name.lower(); target_alias=target.alias_or_name.lower()
            if target_name not in tables:
                raise SQLValidationError('JOIN targets must be loaded tables with detected relationship keys.')
            condition=join.args.get('on')
            if condition is None: raise SQLValidationError('A safe explicit JOIN key is required.')
            # Only a conjunction of plain column equalities is allowed. Merely
            # finding a key equality somewhere inside CASE/COALESCE/OR/etc.
            # does not make that key mandatory for the join.
            leaves=[]
            def flatten_and(node):
                while isinstance(node,exp.Paren): node=node.this
                if isinstance(node,exp.And):
                    flatten_and(node.left);flatten_and(node.right)
                else: leaves.append(node)
            flatten_and(condition)
            safe_relations=[]
            for eq in leaves:
                if not isinstance(eq,exp.EQ) or not isinstance(eq.left,exp.Column) or not isinstance(eq.right,exp.Column):
                    raise SQLValidationError('JOIN conditions must be detected key equalities joined with AND.')
                left_alias=eq.left.table.lower(); right_alias=eq.right.table.lower()
                left_name=scope.get(left_alias); right_name=scope.get(right_alias)
                # Exactly one side must be the table introduced by this JOIN.
                if left_alias==target_alias and right_name:
                    pair=frozenset(((target_name,eq.left.name.lower()),(right_name,eq.right.name.lower())))
                elif right_alias==target_alias and left_name:
                    pair=frozenset(((left_name,eq.left.name.lower()),(target_name,eq.right.name.lower())))
                else:
                    raise SQLValidationError('Every JOIN equality must connect the newly joined table through a detected key.')
                relation=approved.get(pair)
                if not relation: raise SQLValidationError('The JOIN must use a detected key between the newly joined table and an existing table.')
                safe_relations.append(relation)
            if not safe_relations:
                raise SQLValidationError('The JOIN must use a detected key between the newly joined table and an existing table.')
            for relation in safe_relations:
                if relation not in used: used.append(relation)
            scope[target_alias]=target_name
    if require and not used:
        # A query may contain JOINs only in a nested scope, which was validated
        # above; this guard catches malformed/unvisited joins conservatively.
        if list(tree.find_all(exp.Join)):
            raise SQLValidationError('No detected relationship was enforced by the query JOINs.')
    return used

def citations(sql, tables, relationships):
    tree=sqlglot.parse_one(sql,read='duckdb')
    names=sorted({t.name.lower() for t in tree.find_all(exp.Table) if t.name.lower() in tables})
    columns=set()
    try:
        schema={n:{c['name']:'VARCHAR' for c in t.columns} for n,t in tables.items()}
        tree=qualify(tree,dialect='duckdb',schema=schema,validate_qualify_columns=True)
        selects=list(tree.find_all(exp.Select)) or ([tree] if isinstance(tree,exp.Select) else [])
        for select in selects:
            # Resolve identifiers only against tables in this SELECT's direct
            # FROM/JOIN scope. A reused alias in a nested query cannot shadow
            # another SELECT's source mapping.
            source=select.args.get('from_')
            direct=[] if source is None else [source.this]
            direct.extend(join.this for join in (select.args.get('joins') or []))
            aliases={}
            for node in direct:
                if isinstance(node,exp.Table) and node.name.lower() in tables:
                    aliases[node.alias_or_name.lower()]=node.name.lower()
            for column in select.find_all(exp.Column):
                if column.find_ancestor(exp.Select) is not select:continue
                table_name=aliases.get(column.table.lower())
                if table_name:columns.add(f'{table_name}.{column.name.lower()}')
    except Exception: pass
    used=_joined_relationships(tree,tables,relationships,require=bool(list(tree.find_all(exp.Join))))
    return names,sorted(columns),used
