import datetime
import requests
import pymssql
import json
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

import scrapy
from HROrgInfo.items import HrorginfoItem


class HROrgInfoSpider(scrapy.Spider):
    name = "HROrgInfo"

    db = {
        'server': '10.10.0.94',
        'database': 'UCS_ETL',
        'username': 'CLUSER',
        'password': 'Ucredit7607',
        'totb':'ODS_HROrgInfo',
    }
    wbinfo = {
        'main_url':'https://hr.ucs.tw/SCSRwd/api/systemobject/',
        'api_url':'https://hr.ucs.tw/SCSRwd/api/businessobject/',
    }

    def delete(server,username,password,database,totb):
        import pymssql
        conn = pymssql.connect(server=server, user=username, password=password, database = database)
        cursor = conn.cursor()
            
        script = f"""
        delete from  [{totb}]
        """
        cursor.execute(script)
        conn.commit()
        cursor.close()
        conn.close()

    def toSQL(docs, totb, server, database, username, password):
        with pymssql.connect(server=server, user=username, password=password, database=database) as cnxn:
            cnxn.autocommit(False)
            with cnxn.cursor() as cursor:
                data_keys = ','.join(docs[0].keys())
                data_symbols = ','.join(['%s' for _ in range(len(docs[0].keys()))])
                insert_cmd = f"INSERT INTO {totb} ({data_keys}) VALUES ({data_symbols})"
                data_values = [tuple(doc.values()) for doc in docs]
                cursor.executemany(insert_cmd, data_values)
                cnxn.commit()
    

    def NewCash(doc):
        NewCash_Emp= []

        NewCash_Emp.append({
            
            'SYS_VIEWID':doc[0],
            'SYS_NAME':doc[1],
            'SYS_ENGNAME':doc[2],
            'TMP_PDEPARTID':doc[3],
            'TMP_PDEPARTNAME':doc[4],
            'TMP_PDEPARTENGNAME':doc[5],
            'SYS_ID':doc[6],
            'TMP_MANAGERID':doc[7],
            'TMP_MANAGERNAME':doc[8],
            'TMP_MANAGERENGNAME':doc[9],

        })
        return NewCash_Emp

    server,database,username,password,totb= db['server'],db['database'],db['username'],db['password'],db['totb']
    main_url,api_url = wbinfo['main_url'],wbinfo['api_url']



    getdate = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    delete(server,username,password,database,totb)
    print(f'人事資料表-起始時間: {getdate}')

    SenssionID=''        
    headers = {'Content-type': 'application/json'}
    data={
            "Action": "Login",
            "SessionGuid": "",
            "Value":{
                "$type": "AIS.Define.TLogingInputArgs, AIS.Define",
                "CompanyID": "scs164",
                "UserID": "api",
                "Password": "api$1234",
                "LanguageID": "zh-TW"			
            }
    }
    data_json = json.dumps(data)
    response = requests.post(main_url, data=data_json, headers=headers,verify=False)
    result = response.json()

    if result.get('Result'):
        SenssionID = result.get('SessionGuid')
    else :
        print(result.get('Result'),result.get('Message'))

    if SenssionID !="":
        data = {
                "Action": "Find",
                "SessionGuid": SenssionID,
                "ProgID": "HUM0010300",
                "Value": {
                    "$type": "AIS.Define.TFindInputArgs, AIS.Define",
                    "SelectCount": 500,
                    "SelectFields": "SYS_VIEWID,SYS_NAME,SYS_ENGNAME,TMP_PDEPARTID,TMP_PDEPARTNAME,TMP_MANAGERID,TMP_MANAGERNAME",
                    "SystemFilterOptions": "Session,DataPermission,EmployeeLevel",
                    "IsBuildSelectedField": 'true',
                    "IsBuildFlowLightSignalField": 'true'
                }
                }
        data_json = json.dumps(data)
        response = requests.post(api_url, data=data_json, headers=headers,verify=False)
        result =response.json()
        datatype='DataTable'
        data = result.get(datatype)

        for i in range((len(data))):
            SYS_VIEWID = data[i].get('SYS_VIEWID')
            SYS_NAME = data[i].get('SYS_NAME')
            SYS_ENGNAME = data[i].get('SYS_ENGNAME')
            TMP_PDEPARTID = data[i].get('TMP_PDEPARTID')
            TMP_PDEPARTNAME = data[i].get('TMP_PDEPARTNAME')
            TMP_PDEPARTENGNAME = data[i].get('TMP_PDEPARTENGNAME')
            SYS_ID = data[i].get('SYS_ID')
            TMP_MANAGERID = data[i].get('TMP_MANAGERID')
            TMP_MANAGERNAME = data[i].get('TMP_MANAGERNAME')
            TMP_MANAGERENGNAME = data[i].get('TMP_MANAGERENGNAME')




            docs = (SYS_VIEWID,SYS_NAME,SYS_ENGNAME,TMP_PDEPARTID,TMP_PDEPARTNAME,
                    TMP_PDEPARTENGNAME,SYS_ID,TMP_MANAGERID,TMP_MANAGERNAME,TMP_MANAGERENGNAME,)
            NewCash_result = NewCash(docs)
            toSQL(NewCash_result, totb, server, database, username, password)
            continue
