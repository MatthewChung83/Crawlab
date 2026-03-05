import datetime
import requests
import json
import pymssql

import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


import scrapy
from HRUserInfo.items import HruserinfoItem


class HRUserInfoSpider(scrapy.Spider):
    name = "HRUserInfo"

    db = {
        'server': '10.10.0.94',
        'database': 'UCS_ETL',
        'username': 'CLUSER',
        'password': 'Ucredit7607',
        'totb':'ODS_HRUserInfo',

        
    }
    wbinfo = {
        'main_url':'https://hr.ucs.tw/SCSRwd/api/systemobject/',
        'api_url':'https://hr.ucs.tw/SCSRwd/api/businessobject/',
    }

    def NewCash(doc):
        NewCash_Emp= []

        NewCash_Emp.append({
            
            'SYS_ID':doc[0],
            'SYS_COMPANYID':doc[1],
            'TMP_DECCOMPANYID':doc[2],
            'TMP_DECCOMPANYNAME':doc[3],
            'TMP_DECCOMPANYENGNAME':doc[4],
            'DEPARTID':doc[5],
            'DEPARTID2':doc[6],
            'TMP_DEPARTNAME':doc[7],
            'TMP_DEPARTENGNAME':doc[8],
            'SERIAL':doc[9],
            'EMPLOYEEID2':doc[10],
            'EMPLOYEEID':doc[11],
            'EMPLOYEENAME':doc[12],
            'EMPLOYEEENGNAME':doc[13],
            'IDNO':doc[14],
            'JOBSTATUS':doc[15],
            'COUNTRYNAME':doc[16],
            'BIRTHDATE':doc[17],
            'SEX':doc[18],
            'MARRAGE':doc[19],
            'BLOODTYPE':doc[20],
            'BIRTHPLACE':doc[21],
            'OTHER_BIRTHPLACE':doc[22],
            'VTITLEDEPARTID':doc[23],
            'HDEGREE':doc[24],
            'ISTOP':doc[25],
            'STARTDATE':doc[26],
            'WORKINGYEARS':doc[27],
            'SSTARTDATE':doc[28],
            'SPECIALYEARS':doc[29],
            'GARRIVEDATE':doc[30],
            'MOIBLE':doc[31],
            'OFFICETEL1':doc[32],
            'OFFICETEL2':doc[33],
            'PSNEMAI':doc[34],
            'EMAIL1':doc[35],
            'EMAIL2':doc[36],
            'REGTEL':doc[37],
            'REGADDRESS':doc[38],
            'COMMTEL':doc[39],
            'COMMADDRESS':doc[40],
            'EMERGENCYNAME':doc[41],
            'EMERGENCYTELNO':doc[42],
            'EMERGENCYMOBILE':doc[43],
            'EMERGENCYSEX':doc[44],
            'TMP_EMERGENCYID':doc[45],
            'TMP_EMERGENCYNAME':doc[46],
            'JOBCODENAME':doc[47],
            'JOBCODEENGNAME':doc[48],
            'JOBLEVELNAME':doc[49],
            'JOBLEVELENGNAME':doc[50],
            'JOBRANKNAME':doc[51],
            'JOBRANKENGNAME':doc[52],
            'JOBCODEID':doc[53],
            'JOBLEVELID':doc[54],
            'JOBRANKID':doc[55],
            'GD1':doc[56],
            'GD2':doc[57],
            'GD3':doc[58],
            'GD4':doc[59],
            'GD5':doc[60],
            'GD6':doc[61],
            'GD1_ID':doc[62],
            'GD2_ID':doc[63],
            'SELFDEF1':doc[64],
            'SELFDEF2':doc[65],
            'SELFDEF3':doc[66],
            'SELFDEF4':doc[67],
            'SELFDEF5':doc[68],
            'TMP_PROFITID':doc[69],
            'TMP_PROFITNAME':doc[70],
            'TMP_IDYCLASSID':doc[71],
            'TMP_IDYCLASSNAME':doc[72],
            'ISDIRECT':doc[73],
            'ETHNICID':doc[74],
            'ISDISABILITY':doc[75],
            'DISABILITYDEGREE':doc[76],
            'NOTE':doc[77],
            'WORKINGYEARSYMD':doc[78],
            'SELFDEF6':doc[79],
            'SELFDEF7':doc[80],
            'SELFDEF8':doc[81],
            'JOBDESCRIPTION':doc[82],
            'JOBCONTRACT':doc[83],

        })
        return NewCash_Emp

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
        # 提取請假單-get tmp_agentempi
        #getdate = datetime.datetime.now().strftime("%Y/%m/%d")
        #getdate = (datetime.datetime.now()+datetime.timedelta(days=-1)).strftime("%Y/%m/%d")
        #tomorrow = (datetime.datetime.now()+datetime.timedelta(days=1)).strftime("%Y/%m/%d")
        #getdate = '2022/10/21'
        data = {  
        "Action": "ExecReport",
        "SessionGuid": SenssionID,
        "ProgID": "RHUM002",
        "Value": {
            "$type": "AIS.Define.TExecReportInputArgs, AIS.Define",
            "UIType": "Report",
            "ReportID": "",
            "ReportTailID": "",
            "FilterItems": "",
            "UserFilter": ""
        }
        }
        data_json = json.dumps(data)
        response = requests.post(api_url, data=data_json, headers=headers,verify=False)
        result =response.json()
        #print(result)
        datatype='DataSet'
        data = result.get(datatype).get('ReportBody')
        for i in range((len(data))):
            SYS_ID = data[i].get('SYS_ID')
            SYS_COMPANYID = data[i].get('SYS_COMPANYID')
            TMP_DECCOMPANYID = data[i].get('TMP_DECCOMPANYID')
            TMP_DECCOMPANYNAME = data[i].get('TMP_DECCOMPANYNAME')
            TMP_DECCOMPANYENGNAME = data[i].get('TMP_DECCOMPANYENGNAME')
            DEPARTID = data[i].get('DEPARTID')
            DEPARTID2 = data[i].get('DEPARTID2')
            TMP_DEPARTNAME = data[i].get('TMP_DEPARTNAME')
            TMP_DEPARTENGNAME = data[i].get('TMP_DEPARTENGNAME')
            SERIAL = data[i].get('SERIAL')
            EMPLOYEEID2 = data[i].get('EMPLOYEEID2')
            EMPLOYEEID = data[i].get('EMPLOYEEID')
            EMPLOYEENAME = data[i].get('EMPLOYEENAME')
            EMPLOYEEENGNAME = data[i].get('EMPLOYEEENGNAME')
            IDNO = data[i].get('IDNO')
            JOBSTATUS = data[i].get('JOBSTATUS')
            COUNTRYNAME = data[i].get('COUNTRYNAME')
            BIRTHDATE = data[i].get('BIRTHDATE')
            SEX = data[i].get('SEX')
            MARRAGE = data[i].get('MARRAGE')
            BLOODTYPE = data[i].get('BLOODTYPE')
            BIRTHPLACE = data[i].get('BIRTHPLACE')
            OTHER_BIRTHPLACE = data[i].get('OTHER_BIRTHPLACE')
            VTITLEDEPARTID = data[i].get('VTITLEDEPARTID')
            HDEGREE = data[i].get('HDEGREE')
            ISTOP = data[i].get('ISTOP')
            STARTDATE = data[i].get('STARTDATE')
            WORKINGYEARS = data[i].get('WORKINGYEARS')
            SSTARTDATE = data[i].get('SSTARTDATE')
            SPECIALYEARS = data[i].get('SPECIALYEARS')
            GARRIVEDATE = data[i].get('GARRIVEDATE')
            MOIBLE = data[i].get('MOIBLE')
            OFFICETEL1 = data[i].get('OFFICETEL1')
            OFFICETEL2 = data[i].get('OFFICETEL2')
            PSNEMAI = data[i].get('PSNEMAI')
            EMAIL1 = data[i].get('EMAIL1')
            EMAIL2 = data[i].get('EMAIL2')
            REGTEL = data[i].get('REGTEL')
            REGADDRESS = data[i].get('REGADDRESS')
            COMMTEL = data[i].get('COMMTEL')
            COMMADDRESS = data[i].get('COMMADDRESS')
            EMERGENCYNAME = data[i].get('EMERGENCYNAME')
            EMERGENCYTELNO = data[i].get('EMERGENCYTELNO')
            EMERGENCYMOBILE = data[i].get('EMERGENCYMOBILE')
            EMERGENCYSEX = data[i].get('EMERGENCYSEX')
            TMP_EMERGENCYID = data[i].get('TMP_EMERGENCYID')
            TMP_EMERGENCYNAME = data[i].get('TMP_EMERGENCYNAME')
            JOBCODENAME = data[i].get('JOBCODENAME')
            JOBCODEENGNAME = data[i].get('JOBCODEENGNAME')
            JOBLEVELNAME = data[i].get('JOBLEVELNAME')
            JOBLEVELENGNAME = data[i].get('JOBLEVELENGNAME')
            JOBRANKNAME = data[i].get('JOBRANKNAME')
            JOBRANKENGNAME = data[i].get('JOBRANKENGNAME')
            JOBCODEID = data[i].get('JOBCODEID')
            JOBLEVELID = data[i].get('JOBLEVELID')
            JOBRANKID = data[i].get('JOBRANKID')
            GD1 = data[i].get('GD1')
            GD2 = data[i].get('GD2')
            GD3 = data[i].get('GD3')
            GD4 = data[i].get('GD4')
            GD5 = data[i].get('GD5')
            GD6 = data[i].get('GD6')
            GD1_ID = data[i].get('GD1_ID')
            GD2_ID = data[i].get('GD2_ID')
            SELFDEF1 = data[i].get('SELFDEF1')
            SELFDEF2 = data[i].get('SELFDEF2')
            SELFDEF3 = data[i].get('SELFDEF3')
            SELFDEF4 = data[i].get('SELFDEF4')
            SELFDEF5 = data[i].get('SELFDEF5')
            TMP_PROFITID = data[i].get('TMP_PROFITID')
            TMP_PROFITNAME = data[i].get('TMP_PROFITNAME')
            TMP_IDYCLASSID = data[i].get('TMP_IDYCLASSID')
            TMP_IDYCLASSNAME = data[i].get('TMP_IDYCLASSNAME')
            ISDIRECT = data[i].get('ISDIRECT')
            ETHNICID = data[i].get('ETHNICID')
            ISDISABILITY = data[i].get('ISDISABILITY')
            DISABILITYDEGREE = data[i].get('DISABILITYDEGREE')
            NOTE = data[i].get('NOTE')
            WORKINGYEARSYMD = data[i].get('WORKINGYEARSYMD')
            SELFDEF6 = data[i].get('SELFDEF6')
            SELFDEF7 = data[i].get('SELFDEF7')
            SELFDEF8 = data[i].get('SELFDEF8')
            JOBDESCRIPTION = data[i].get('JOBDESCRIPTION')
            JOBCONTRACT = data[i].get('JOBCONTRACT')



            docs = (SYS_ID,SYS_COMPANYID,TMP_DECCOMPANYID,TMP_DECCOMPANYNAME,TMP_DECCOMPANYENGNAME,DEPARTID,DEPARTID2,
                    TMP_DEPARTNAME,TMP_DEPARTENGNAME,SERIAL,EMPLOYEEID2,EMPLOYEEID,EMPLOYEENAME,EMPLOYEEENGNAME,IDNO,
                    JOBSTATUS,COUNTRYNAME,BIRTHDATE,SEX,MARRAGE,BLOODTYPE,BIRTHPLACE,OTHER_BIRTHPLACE,VTITLEDEPARTID,
                    HDEGREE,ISTOP,STARTDATE,WORKINGYEARS,SSTARTDATE,SPECIALYEARS,GARRIVEDATE,MOIBLE,OFFICETEL1,OFFICETEL2,
                    PSNEMAI,EMAIL1,EMAIL2,REGTEL,REGADDRESS,COMMTEL,COMMADDRESS,EMERGENCYNAME,EMERGENCYTELNO,EMERGENCYMOBILE,
                    EMERGENCYSEX,TMP_EMERGENCYID,TMP_EMERGENCYNAME,JOBCODENAME,JOBCODEENGNAME,JOBLEVELNAME,JOBLEVELENGNAME,
                    JOBRANKNAME,JOBRANKENGNAME,JOBCODEID,JOBLEVELID,JOBRANKID,GD1,GD2,GD3,GD4,GD5,GD6,GD1_ID,GD2_ID,SELFDEF1,
                    SELFDEF2,SELFDEF3,SELFDEF4,SELFDEF5,TMP_PROFITID,TMP_PROFITNAME,TMP_IDYCLASSID,TMP_IDYCLASSNAME,ISDIRECT,
                    ETHNICID,ISDISABILITY,DISABILITYDEGREE,NOTE,WORKINGYEARSYMD,SELFDEF6,SELFDEF7,SELFDEF8,JOBDESCRIPTION,
                    JOBCONTRACT)
            NewCash_result = NewCash(docs)
            toSQL(NewCash_result, totb, server, database, username, password)
            continue
