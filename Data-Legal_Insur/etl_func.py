# -*- coding: utf-8 -*-
"""
Database ETL functions for Legal Insurance System
"""
import pymssql


def foo(num, obs):
    """Generator function for iteration"""
    while num < obs:
        num = num + 1
        yield num


def src_obs(server, username, password, database, fromtb, totb,today):
    """Get count of pending cases (STATUS = 'N')"""
    conn = pymssql.connect(server=server, user=username, password=password, database=database, charset='utf8')
    cursor = conn.cursor()
    script = f"""
    SELECT COUNT(*) FROM INS_Legal_Insurtech WHERE STATUS = 'N' AND DataDt = '{today}'
    """
    cursor.execute(script)
    obs = cursor.fetchall()
    cursor.close()
    conn.close()
    return list(obs[0])[0]


def dbfrom(server, username, password, database, fromtb, totb, today):
    """Fetch one pending case data from database"""
    conn = pymssql.connect(server=server, user=username, password=password, database=database, charset='utf8')
    cursor = conn.cursor()

    script = f"""
    WITH data AS (
        SELECT
            [UUID]
            ,[DataDate]
            ,[LDCI]
            ,[CaseI]
            ,[DebtorName]
            ,[Legal_Num]
            ,[Legal_Court]
            ,STUFF((SELECT ',' + [DebtorID]
                FROM [INS_Legal_Insurtech]
                WHERE CaseI = s.CaseI AND DataDt = '{today}'
                FOR XML PATH('')), 1, 1, '') AS [DebtorID]
            ,[Order_Num]
            ,[Transfer_Bank]
            ,[Transfer_Account]
            ,[Transfer_Fee]
            ,[Payment_Type]
            ,[Product_List]
            ,[Payment_Deadline]
            ,[Account_Name]
            ,[Legal_Type]
            ,[Insur_Type]
            ,[Notes]
            ,[ApplyName]
            ,[STATUS]
            ,[DataDt]
            ,seq = ROW_NUMBER() OVER(PARTITION BY s.casei ORDER BY s.[DebtorID])
        FROM [UCS_ReportDB].[dbo].[INS_Legal_Insurtech] s
        WHERE STATUS = 'N' AND DataDt = '{today}'
    )
    SELECT * FROM data WHERE seq = 1
    ORDER BY Casei
    OFFSET 0 ROW FETCH NEXT 1 ROWS ONLY
    """
    cursor.execute(script)
    c_src = cursor.fetchall()

    cursor.close()
    conn.close()
    return c_src


def update(server, username, password, database, totb, Notes, Casei, Order_Num, Account_Name,
           Payment_Type, Product_List, Transfer_Bank, Transfer_Account, Payment_Deadline,
           Transfer_Fee, Legal_Type, Status, today):
    """Update case information in database"""
    conn = pymssql.connect(server=server, user=username, password=password, database=database, charset='utf8')
    cursor = conn.cursor()

    script = f"""
    UPDATE [{totb}]
    SET Notes = '{Notes}',
        Order_Num = '{Order_Num}',
        Account_Name = '{Account_Name}',
        Payment_Type = '{Payment_Type}',
        Product_List = '{Product_List}',
        Transfer_Bank = '{Transfer_Bank}',
        Transfer_Account = '{Transfer_Account}',
        Payment_Deadline = '{Payment_Deadline}',
        Transfer_Fee = '{Transfer_Fee}',
        Legal_Type = '{Legal_Type}',
        Status = '{Status}'
    WHERE casei = '{Casei}' AND DataDt = '{today}'
    """
    cursor.execute(script)
    conn.commit()
    cursor.close()
    conn.close()
