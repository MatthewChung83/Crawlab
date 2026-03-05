# -*- coding: utf-8 -*-
"""
Created on Mon May  9 18:34:52 2022

@author: admin
"""

def foo(num,obs):
    while num < obs:
        num = num + 1 
        yield num
def src_obs(server,username,password,database,fromtb,totb):
    import pymssql
    conn = pymssql.connect(server=server, user=username, password=password, database = database)
    cursor = conn.cursor()
    script = f"""
    
    select ( select count(*) from base_case_allID b
            left join judicial_fam r on b.ID = r.ID 
            where r.ID is null )
   +
    (select count(*) from judicial_fam 
    where (select DATEDIFF(mm, update_date, getdate()))> = 3 )  
	 
    """    
    cursor.execute(script)
    obs = cursor.fetchall()
    cursor.close()
    conn.close()
    return list(obs[0])[0]
def judicial(doc):
    judicial= []

    judicial.append({
        "Name":doc[0],
        "ID":doc[1],
        "announcement":doc[2],
        "post_date":doc[3],
        "register_no":doc[4],
        "keynote":doc[5],
        "Basis":doc[6],
        "Matters":doc[7],
        "update_date":doc[8],
        "note":doc[9],
        "flag":doc[10],
        "note2":doc[11],
    })
    return judicial
def toSQL(docs, totb, server, database, username, password):
    import pymssql

    with pymssql.connect(server=server, user=username, password=password, database=database) as conn:
        with conn.cursor() as cursor:
            data_keys = ','.join(docs[0].keys())
            data_symbols = ','.join(['%s' for _ in docs[0].keys()])
            insert_cmd = f"INSERT INTO {totb} ({data_keys}) VALUES ({data_symbols})"
            data_values = [tuple(doc.values()) for doc in docs]
            cursor.executemany(insert_cmd, data_values)
        conn.commit()


def dbfrom(server,username,password,database,fromtb,totb):
    import pymssql
    conn = pymssql.connect(server=server, user=username, password=password, database = database)
    cursor = conn.cursor()
    
    script = f"""
    select distinct b.personi,b.ID,replace(convert(varchar(10),b.name),'?','') as name,b.casei,b.type,b.c,b.m,b.age,b.flg,r.rowid
    into #test
    from {fromtb} b
	left join [{totb}] r on b.ID = r.ID 
	where r.ID is null and r.ID != 'C220263848'
    
    
    insert into #test
    select distinct 0 as personi,ID,replace(convert(varchar(10),name),'?','')as name,0 as casei,0 as type,0 as c,0 as m,0 as age,'' as flg,rowid
    from [{totb}]
    where (select DATEDIFF(mm, update_date, getdate()))> = 3 and ID != 'C220263848'
	
    select * from #test order by flg desc 
	--offset 0 row fetch next 1 rows only
    
    """
    cursor.execute(script)
    c_src = cursor.fetchall()
    
    cursor.close()
    conn.close()
    return c_src

def delete(server,username,password,database,totb,note,ID,rowid,register_no,item):
    import pymssql
    conn = pymssql.connect(server=server, user=username, password=password, database = database)
    cursor = conn.cursor()
        
    script = f"""
    delete from [{totb}]
    where id = '{ID}'  --and register_no = '{register_no}' and flag = '{item}'
    
    """
    cursor.execute(script)
    conn.commit()
    cursor.close()
    conn.close()
def exit_obs(server,username,password,database,totb):
    import pymssql
    conn = pymssql.connect(server=server, user=username, password=password, database = database)
    cursor = conn.cursor()
    script = f"""
    select count (distinct ID)
    from [{totb}]
    where  update_date > = convert(varchar(10),getdate(),111)
    """    
    cursor.execute(script)
    obs = cursor.fetchall()
    cursor.close()
    conn.close()
    return list(obs[0])[0]