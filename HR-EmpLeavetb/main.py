import datetime
import requests
import json
import scrapy
from empleavetb.items import EmpleavetbItem


class empleavetbSpider(scrapy.Spider):
    name = "empleavetb"
    
    db = {
        'server': '10.10.0.94',
        'database': 'CL_Daily',
        'username': 'CLUSER',
        'password': 'Ucredit7607',
        'totb':'empleave_tmp_tb',
    }
    wbinfo = {
        'main_url':'https://hr.ucs.tw/SCSRwd/api/systemobject/',
        'api_url':'https://hr.ucs.tw/SCSRwd/api/businessobject/',
    }
    server,database,username,password,totb= db['server'],db['database'],db['username'],db['password'],db['totb']
    main_url,api_url = wbinfo['main_url'],wbinfo['api_url']
    getdate = datetime.date.today()
    getdate = str(getdate).replace('-','/')
    print(f'請假記錄同步-起始時間: {getdate}')

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
    response = requests.post(main_url, data=data_json, headers=headers)
    result = response.json()

    if result.get('Result'):
        SenssionID = result.get('SessionGuid')
    else :
        print(result.get('Result'),result.get('Message'))


    if SenssionID !="":
        data = {  
        "Action": "ExecReport",
        "SessionGuid": SenssionID,
        "ProgID": "RATT004",
        "Value": {
            "$type": "AIS.Define.TExecReportInputArgs, AIS.Define",
            "UIType": "Report",
            "ReportID": "",
            "ReportTailID": "",
            "FilterItems": [
            {
                "$type": "AIS.Define.TFilterItem, AIS.Define",
                "FieldName": "A.SYS_CompanyID",
                "FilterValue": "SCS164"
            },
            
            {
                "$type": "AIS.Define.TFilterItem, AIS.Define",
                "FieldName": "IsNull(DT.StartDate, D.StartDate)",
                "FilterValue": getdate,
                "ComparisonOperator": "GreaterOrEqual"
            }
            ],
            "UserFilter": ""
        }
        }
        data_json = json.dumps(data)
        response = requests.post(api_url, data=data_json, headers=headers)
        result =response.json()
        datatype='DataSet'
        data = result.get(datatype).get('ReportBody')

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
            """
            將數據寫入 MSSQL 資料庫，使用 pymssql 實現
            """
            import pymssql

            # 連接到 MSSQL
            with pymssql.connect(server=server, user=username, password=password, database=database) as conn:
                conn.autocommit(False)  # 關閉自動提交
                with conn.cursor() as cursor:
                    # 構建 INSERT SQL 語句
                    data_keys = ','.join(docs[0].keys())  # 提取欄位名稱
                    data_symbols = ','.join(['%s' for _ in range(len(docs[0].keys()))])  # 對應佔位符
                    insert_cmd = f"INSERT INTO {totb} ({data_keys}) VALUES ({data_symbols})"
                    
                    # 準備數據值
                    data_values = [tuple(doc.values()) for doc in docs]
                    
                    try:
                        # 插入數據
                        cursor.executemany(insert_cmd, data_values)
                        conn.commit()  # 提交變更
                        print("數據已成功插入！")
                    except Exception as e:
                        conn.rollback()  # 如果出現錯誤，回滾
                        print(f"插入數據時出現錯誤: {e}")

                
        def empleave_tmp_tb(doc):
            empleave_tmp_tb= []

            empleave_tmp_tb.append({
                
                'LEAVETYPE':doc[0], 
                'SYS_COMPANYID':doc[1],
                'TMP_DECCOMPANYID':doc[2],
                'TMP_DECCOMPANYNAME':doc[3],
                'TMP_DECCOMPANYENGNAME':doc[4],
                'DEPARTID':doc[5],
                'DEPARTID2':doc[6],
                'DEPARTNAME':doc[7],
                'DEPARTENGNAME':doc[8],
                'EMPLOYEEID':doc[9],
                'EMPLOYEENAME':doc[10],
                'SYS_ENGNAME':doc[11],
                'SEX':doc[12],
                'SYS_VIEWID':doc[13],
                'SYS_DATE':doc[14],
                'VACATIONID':doc[15],
                'VACATIONNAME':doc[16],
                'VACATIONENGNAME':doc[17],
                'SVACATIONID':doc[18],
                'SVACATIONNAME':doc[19],
                'SVACATIONENGNAME':doc[20],
                'STARTDATE':doc[21],
                'STARTTIME':doc[22],
                'ENDDATE':doc[23],
                'ENDTIME':doc[24],
                'LEAVEDAYS':doc[25],
                'LEAVEHOURS':doc[26],
                'LEAVEMINUTES':doc[27],
                'HOURWAGES':doc[28],
                'LEAVEMONEY':doc[29],
                'AGENTID':doc[30],
                'AGENTNAME':doc[31],
                'MAINNOTE':doc[32],
                'SUBNOTE':doc[33],
                'SYS_FLOWFORMSTATUS':doc[34],
                'OFFLEAVEDAYS':doc[35],
                'OFFLEAVEHOURS':doc[36],
                'OFFLEAVEMINUTES':doc[37],
                'REALLEAVEDAYS':doc[38],
                'REALLEAVEHOURS':doc[39],
                'REALLEAVEMINUTES':doc[40],
                'CUTDATE':doc[41],
                'SPECIALDATE':doc[42],
                'STARGETNAME':doc[43], 
                'SENDDATE':doc[44],
                'SOURCETAG':doc[45],
                'OUTSIDENAME':doc[46],
                'OUTSIDETEL':doc[47],
                'ISLEAVE':doc[48],
                'ISCOMEBACK':doc[49],
                'EMPTEL':doc[50],
                'RESTPLACE':doc[51],
                'EMPADDRESS':doc[52],
                'NOTE2':doc[53],
                'PRJOECTID':doc[54],
                'TMP_PRJOECTID':doc[55],
                'TMP_PRJOECTNAME':doc[56],
                'TMP_PRJOECTENGNAME':doc[57],
                'DIRECTID':doc[58],
                'TMP_DIRECTID':doc[59],
                'PMANAGERID':doc[60],
                'TMP_PMANAGERID':doc[61],
                'APPROVER3ID':doc[62],
                'TMP_APPROVER3ID':doc[63],
                'APPROVER4ID':doc[64],
                'TMP_APPROVER4ID':doc[65],
                'GD1':doc[66],
                'GD2':doc[67],
                'GD3':doc[68],
                'GD4':doc[69],
                'GD5':doc[70],
                'GD6':doc[71],
                'VACATIONTYPEID':doc[72],
                'VACATIONTYPENAME':doc[73],
                'VACATIONTYPEENGNAME':doc[74],
                'CDEPARTID':doc[75],
                'CDEPARTNAME':doc[76],
                'CDEPARTENGNAME':doc[77],
                'insertdate':doc[78],
                'update_date':doc[79],
            })
            return empleave_tmp_tb
        delete(server,username,password,database,totb)
        for i in range((len(data))):
            LEAVETYPE = data[i].get('LEAVETYPE')
            SYS_COMPANYID = data[i].get('SYS_COMPANYID')
            TMP_DECCOMPANYID = data[i].get('TMP_DECCOMPANYID')
            TMP_DECCOMPANYNAME = data[i].get('TMP_DECCOMPANYNAME')
            TMP_DECCOMPANYENGNAME = data[i].get('TMP_DECCOMPANYENGNAME')
            DEPARTID = data[i].get('DEPARTID')
            DEPARTID2 = data[i].get('DEPARTID2')
            DEPARTNAME = data[i].get('DEPARTNAME')
            DEPARTENGNAME = data[i].get('DEPARTENGNAME')
            EMPLOYEEID = data[i].get('EMPLOYEEID') 
            EMPLOYEENAME = data[i].get('EMPLOYEENAME')
            SYS_ENGNAME = data[i].get('SYS_ENGNAME')
            SEX = data[i].get('SEX')
            SYS_VIEWID = data[i].get('SYS_VIEWID')
            SYS_DATE = data[i].get('SYS_DATE')
            VACATIONID = data[i].get('VACATIONID')
            VACATIONNAME = data[i].get('VACATIONNAME')
            VACATIONENGNAME = data[i].get('VACATIONENGNAME') 
            SVACATIONID = data[i].get('SVACATIONID')
            SVACATIONNAME = data[i].get('SVACATIONNAME') 
            SVACATIONENGNAME = data[i].get('SVACATIONENGNAME')
            STARTDATE = data[i].get('STARTDATE')
            STARTTIME = data[i].get('STARTTIME') 
            ENDDATE = data[i].get('ENDDATE') 
            ENDTIME = data[i].get('ENDTIME') 
            LEAVEDAYS = data[i].get('LEAVEDAYS') 
            LEAVEHOURS = data[i].get('LEAVEHOURS')
            LEAVEMINUTES = data[i].get('LEAVEMINUTES')
            HOURWAGES = data[i].get('HOURWAGES') 
            LEAVEMONEY = data[i].get('LEAVEMONEY')
            AGENTID = data[i].get('AGENTID') 
            AGENTNAME = data[i].get('AGENTNAME')
            MAINNOTE = data[i].get('MAINNOTE') 
            SUBNOTE = data[i].get('SUBNOTE')
            SYS_FLOWFORMSTATUS = data[i].get('SYS_FLOWFORMSTATUS')
            OFFLEAVEDAYS = data[i].get('OFFLEAVEDAYS')
            OFFLEAVEHOURS = data[i].get('OFFLEAVEHOURS')
            OFFLEAVEMINUTES = data[i].get('OFFLEAVEMINUTES')
            REALLEAVEDAYS = data[i].get('REALLEAVEDAYS')
            REALLEAVEHOURS = data[i].get('REALLEAVEHOURS')
            REALLEAVEMINUTES = data[i].get('REALLEAVEMINUTES')
            CUTDATE = data[i].get('CUTDATE') 
            SPECIALDATE = data[i].get('SPECIALDATE')
            STARGETNAME = data[i].get('STARGETNAME')
            SENDDATE = data[i].get('SENDDATE')
            SOURCETAG = data[i].get('SOURCETAG') 
            OUTSIDENAME = data[i].get('OUTSIDENAME') 
            OUTSIDETEL = data[i].get('OUTSIDETEL')
            ISLEAVE = data[i].get('ISLEAVE') 
            ISCOMEBACK = data[i].get('ISCOMEBACK')
            EMPTEL = data[i].get('EMPTEL') 
            RESTPLACE = data[i].get('RESTPLACE')
            EMPADDRESS = data[i].get('EMPADDRESS')
            NOTE2 = data[i].get('NOTE2')
            PRJOECTID = data[i].get('PRJOECTID')
            TMP_PRJOECTID = data[i].get('TMP_PRJOECTID')
            TMP_PRJOECTNAME = data[i].get('TMP_PRJOECTNAME')
            TMP_PRJOECTENGNAME = data[i].get('TMP_PRJOECTENGNAME')
            DIRECTID = data[i].get('DIRECTID')
            TMP_DIRECTID = data[i].get('TMP_DIRECTID') 
            PMANAGERID = data[i].get('PMANAGERID')
            TMP_PMANAGERID = data[i].get('TMP_PMANAGERID') 
            APPROVER3ID = data[i].get('APPROVER3ID')
            TMP_APPROVER3ID = data[i].get('TMP_APPROVER3ID') 
            APPROVER4ID = data[i].get('APPROVER4ID') 
            TMP_APPROVER4ID = data[i].get('TMP_APPROVER4ID') 
            GD1 = data[i].get('GD1') 
            GD2 = data[i].get('GD2') 
            GD3 = data[i].get('GD3')
            GD4 = data[i].get('GD4') 
            GD5 = data[i].get('GD5')
            GD6 = data[i].get('GD6') 
            VACATIONTYPEID = data[i].get('VACATIONTYPEID')
            VACATIONTYPENAME = data[i].get('VACATIONTYPENAME')
            VACATIONTYPEENGNAME = data[i].get('VACATIONTYPEENGNAME')
            CDEPARTID = data[i].get('CDEPARTID')
            CDEPARTNAME = data[i].get('CDEPARTNAME') 
            CDEPARTENGNAME = data[i].get('CDEPARTENGNAME')
            insertdate = getdate
            update_date = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            docs = (LEAVETYPE,SYS_COMPANYID,TMP_DECCOMPANYID,TMP_DECCOMPANYNAME,
                    TMP_DECCOMPANYENGNAME,DEPARTID,DEPARTID2,DEPARTNAME,DEPARTENGNAME,
                    EMPLOYEEID, EMPLOYEENAME, SYS_ENGNAME, SEX, SYS_VIEWID, SYS_DATE, 
                    VACATIONID, VACATIONNAME, VACATIONENGNAME, SVACATIONID, SVACATIONNAME, 
                    SVACATIONENGNAME, STARTDATE, STARTTIME, ENDDATE, ENDTIME, LEAVEDAYS, 
                    LEAVEHOURS, LEAVEMINUTES, HOURWAGES, LEAVEMONEY, AGENTID, AGENTNAME, 
                    MAINNOTE, SUBNOTE, SYS_FLOWFORMSTATUS, OFFLEAVEDAYS, OFFLEAVEHOURS, 
                    OFFLEAVEMINUTES, REALLEAVEDAYS, REALLEAVEHOURS, REALLEAVEMINUTES, 
                    CUTDATE, SPECIALDATE, STARGETNAME, SENDDATE, SOURCETAG, OUTSIDENAME, 
                    OUTSIDETEL, ISLEAVE, ISCOMEBACK, EMPTEL, RESTPLACE, EMPADDRESS, 
                    NOTE2, PRJOECTID, TMP_PRJOECTID, TMP_PRJOECTNAME, TMP_PRJOECTENGNAME, 
                    DIRECTID, TMP_DIRECTID, PMANAGERID, TMP_PMANAGERID, APPROVER3ID, 
                    TMP_APPROVER3ID, APPROVER4ID, TMP_APPROVER4ID, GD1, GD2, GD3, 
                    GD4, GD5, GD6, VACATIONTYPEID, VACATIONTYPENAME, VACATIONTYPEENGNAME, 
                    CDEPARTID, CDEPARTNAME, CDEPARTENGNAME,insertdate,update_date)
            #print(docs)
            print(empleave_tmp_tb(docs))
            empleave_tmp_tb_result = empleave_tmp_tb(docs)
            
            toSQL(empleave_tmp_tb_result, totb, server, database, username, password)

