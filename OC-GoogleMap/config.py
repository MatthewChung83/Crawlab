# -*- coding: utf-8 -*-
"""
Configuration for OC-GoogleMap - OC visit case data sync to Google Maps
"""

db = {
    'server': '10.10.0.94',
    'database': 'CL_Daily',
    'username': 'CLUSER',
    'password': 'Ucredit7607',
}

ssh = {
    'server': '10.10.0.66',
    'port': 22,
    'username': 'uicts',
    'password': 'Ucs@28289788',
    'local_folder': '/tmp/OCMAP',
    'remote_folder': '/home/uicts/cash',
}

google = {
    'email': '10773016@gm.scu.edu.tw',
    'password': '0000007740',
}

# OC list for data export
OC_LIST = [
    'ALEXY', 'ANDERSON', 'KEVIN4584', 'JACKYH', 'JASON4703',
    'JULIAN', 'SCOTT4162', 'SIMONSH', 'SPANELY', 'WHITE5082'
]

# Google Maps URL list (url, oc_name)
URL_LIST = [
    ('https://accounts.google.com/v3/signin/identifier?dsh=S-1593203054%3A1681712270285015&continue=https%3A%2F%2Fwww.google.com%2Fmaps%2Fd%2Fviewer%3Fhl%3Dzh-TW%26mid%3D1uYIgPtwrNX2S7zqsKhw6Ryj_3kjqWUw%26ll%3D24.04740285808056%2C120.10402299999998%26z%3D7&ec=GAZA2gE&followup=https%3A%2F%2Fwww.google.com%2Fmaps%2Fd%2Fviewer%3Fhl%3Dzh-TW%26mid%3D1uYIgPtwrNX2S7zqsKhw6Ryj_3kjqWUw%26ll%3D24.04740285808056%2C120.10402299999998%26z%3D7&hl=zh-TW&ifkv=AQMjQ7T6aNN_tYqzul15RPFNc8W25AGqbOmKeKdf3L2cgEg413d7oqUAtB4PMa0BzyMTLa1iI1MRkQ&passive=1209600&flowName=GlifWebSignIn&flowEntry=ServiceLogin', 'ALEXY'),
    ('https://accounts.google.com/v3/signin/identifier?dsh=S655048351%3A1681711320362031&continue=https%3A%2F%2Fwww.google.com%2Fmaps%2Fd%2Fviewer%3Fhl%3Dzh-TW%26mid%3D1qblXja7GTajvC4B282yFr8Xw9XPi26E%26ll%3D24.04740285808056%2C120.10402299999998%26z%3D7&ec=GAZA2gE&followup=https%3A%2F%2Fwww.google.com%2Fmaps%2Fd%2Fviewer%3Fhl%3Dzh-TW%26mid%3D1qblXja7GTajvC4B282yFr8Xw9XPi26E%26ll%3D24.04740285808056%2C120.10402299999998%26z%3D7&hl=zh-TW&ifkv=AQMjQ7R_rfrdycglT3XenTu7AKFfPXLEiY2Bx2awTQB_-O7l0_1FOurkuZXk9BwT_q80EmtCQeUu1Q&passive=1209600&flowName=GlifWebSignIn&flowEntry=ServiceLogin', 'ANDERSON'),
    ('https://accounts.google.com/v3/signin/identifier?dsh=S-234206541%3A1681711357745882&continue=https%3A%2F%2Fwww.google.com%2Fmaps%2Fd%2Fviewer%3Fhl%3Dzh-TW%26mid%3D1zhUvtlOXuzHbdAePLMLG6hcQsZTXWeg%26ll%3D24.04740285808056%2C120.10402299999998%26z%3D7&ec=GAZA2gE&followup=https%3A%2F%2Fwww.google.com%2Fmaps%2Fd%2Fviewer%3Fhl%3Dzh-TW%26mid%3D1zhUvtlOXuzHbdAePLMLG6hcQsZTXWeg%26ll%3D24.04740285808056%2C120.10402299999998%26z%3D7&hl=zh-TW&ifkv=AQMjQ7QGizQqGu1ufOj2OkCJ8gzd7PCHiCKaYrhuY8_zgKpTZPO4LeHttY0SQvJ76I9_NRSIbQOfwQ&passive=1209600&flowName=GlifWebSignIn&flowEntry=ServiceLogin', 'BEN4423'),
    ('https://accounts.google.com/v3/signin/identifier?dsh=S1275321292%3A1681711409025665&continue=https%3A%2F%2Fwww.google.com%2Fmaps%2Fd%2Fviewer%3Fhl%3Dzh-TW%26mid%3D1wrFPoRKpm2Ldj2hzrbIh3aGf3A2mwUU%26ll%3D24.04740285808056%2C120.10402299999998%26z%3D7&ec=GAZA2gE&followup=https%3A%2F%2Fwww.google.com%2Fmaps%2Fd%2Fviewer%3Fhl%3Dzh-TW%26mid%3D1wrFPoRKpm2Ldj2hzrbIh3aGf3A2mwUU%26ll%3D24.04740285808056%2C120.10402299999998%26z%3D7&hl=zh-TW&ifkv=AQMjQ7TDXRLFPjFpl1wVS4eo79b22-W4jH3XS3DJr09TGjBFSt7OnnzbMbEuL7elvIyX-XhMZgE3&passive=1209600&flowName=GlifWebSignIn&flowEntry=ServiceLogin', 'KEVIN4584'),
    ('https://accounts.google.com/v3/signin/identifier?dsh=S1242336415%3A1681711438748969&continue=https%3A%2F%2Fwww.google.com%2Fmaps%2Fd%2Fviewer%3Fhl%3Dzh-TW%26mid%3D1MQwYjQuvQ7qjl4VYym8_aTOl5APqBzA%26ll%3D24.04740285808056%2C120.10402299999998%26z%3D7&ec=GAZA2gE&followup=https%3A%2F%2Fwww.google.com%2Fmaps%2Fd%2Fviewer%3Fhl%3Dzh-TW%26mid%3D1MQwYjQuvQ7qjl4VYym8_aTOl5APqBzA%26ll%3D24.04740285808056%2C120.10402299999998%26z%3D7&hl=zh-TW&ifkv=AQMjQ7QSFjDh2Q0o5AjbjzRRCWDVE7MQPjpxZeg1yPtLwj2jyUuAV0Dom5yFHWCIiaeY5zdN3JMixw&passive=1209600&flowName=GlifWebSignIn&flowEntry=ServiceLogin', 'JACKYH'),
    ('https://accounts.google.com/v3/signin/identifier?dsh=S386651260%3A1681711519884945&continue=https%3A%2F%2Fwww.google.com%2Fmaps%2Fd%2Fviewer%3Fhl%3Dzh-TW%26mid%3D11bK3P3DlFTIc3GQHyNY0Yo7Kf5e8fHk%26ll%3D24.04740285808056%2C120.10402299999998%26z%3D7&ec=GAZA2gE&followup=https%3A%2F%2Fwww.google.com%2Fmaps%2Fd%2Fviewer%3Fhl%3Dzh-TW%26mid%3D11bK3P3DlFTIc3GQHyNY0Yo7Kf5e8fHk%26ll%3D24.04740285808056%2C120.10402299999998%26z%3D7&hl=zh-TW&ifkv=AQMjQ7RCssIJynCbGUnLhQih0CJ0FT-CwwEFXxJYacYsOsrLdKzrob_rWJhsLt3nwuXZOxK53aDrRQ&passive=1209600&flowName=GlifWebSignIn&flowEntry=ServiceLogin', 'JASON4703'),
    ('https://accounts.google.com/v3/signin/identifier?dsh=S1224916245%3A1681711553453460&continue=https%3A%2F%2Fwww.google.com%2Fmaps%2Fd%2Fviewer%3Fhl%3Dzh-TW%26mid%3D1IcBH4h2YkL9HBqzWFkqBIy7Qm6CTh6o%26ll%3D24.04740285808056%2C120.10402299999998%26z%3D7&ec=GAZA2gE&followup=https%3A%2F%2Fwww.google.com%2Fmaps%2Fd%2Fviewer%3Fhl%3Dzh-TW%26mid%3D1IcBH4h2YkL9HBqzWFkqBIy7Qm6CTh6o%26ll%3D24.04740285808056%2C120.10402299999998%26z%3D7&hl=zh-TW&ifkv=AQMjQ7SIsu2PSmBMPcx3MyxQvTc4gH3HB1tCc8PNoD3TYAm5dLwRlrQdSboxJSr3RgGZRNzN-av0eA&passive=1209600&flowName=GlifWebSignIn&flowEntry=ServiceLogin', 'JULIAN'),
    ('https://accounts.google.com/v3/signin/identifier?dsh=S83959985%3A1681711596526038&continue=https%3A%2F%2Fwww.google.com%2Fmaps%2Fd%2Fviewer%3Fhl%3Dzh-TW%26mid%3D11gvbigwoSC6U_Y7z0446IiqHje9FT34%26ll%3D24.04740285808056%2C120.10402299999998%26z%3D7&ec=GAZA2gE&followup=https%3A%2F%2Fwww.google.com%2Fmaps%2Fd%2Fviewer%3Fhl%3Dzh-TW%26mid%3D11gvbigwoSC6U_Y7z0446IiqHje9FT34%26ll%3D24.04740285808056%2C120.10402299999998%26z%3D7&hl=zh-TW&ifkv=AQMjQ7TFQdAK4N0FyXqg0Un8xer3exnIhaVGZTSlPV3FRFVwxC_VYNqY8lEVLQzXKXCFgO8ryE4J9A&passive=1209600&flowName=GlifWebSignIn&flowEntry=ServiceLogin', 'SCOTT4162'),
    ('https://accounts.google.com/v3/signin/identifier?dsh=S-872058158%3A1681711634509817&continue=https%3A%2F%2Fwww.google.com%2Fmaps%2Fd%2Fviewer%3Fhl%3Dzh-TW%26mid%3D1VFjbRpmUbUL0xGeat1d9ISw4YvJIvCg%26ll%3D24.04740285808056%2C120.10402299999998%26z%3D7&ec=GAZA2gE&followup=https%3A%2F%2Fwww.google.com%2Fmaps%2Fd%2Fviewer%3Fhl%3Dzh-TW%26mid%3D1VFjbRpmUbUL0xGeat1d9ISw4YvJIvCg%26ll%3D24.04740285808056%2C120.10402299999998%26z%3D7&hl=zh-TW&ifkv=AQMjQ7TVZsuRtUMX90I7YNdvAxVhQdtvLBge9YW_9XORTvZgXw55JzXV8foUdrZG1oXZI0DtJqv9PA&passive=1209600&flowName=GlifWebSignIn&flowEntry=ServiceLogin', 'SIMONSH'),
    ('https://accounts.google.com/v3/signin/identifier?dsh=S-855169725%3A1681711726026711&continue=https%3A%2F%2Fwww.google.com%2Fmaps%2Fd%2Fviewer%3Fhl%3Dzh-TW%26mid%3D1n1cC11Z989d_MgiYGFKsf3uYc4rmGLY%26ll%3D24.04740285808056%2C120.10402299999998%26z%3D7&ec=GAZA2gE&followup=https%3A%2F%2Fwww.google.com%2Fmaps%2Fd%2Fviewer%3Fhl%3Dzh-TW%26mid%3D1n1cC11Z989d_MgiYGFKsf3uYc4rmGLY%26ll%3D24.04740285808056%2C120.10402299999998%26z%3D7&hl=zh-TW&ifkv=AQMjQ7TEnaEzsAO2L0OFX-GzKMeFFPSD4KDneY5cvcnhl42DB2RvbnEDxAh8lOl58rcjfgao97th&passive=1209600&flowName=GlifWebSignIn&flowEntry=ServiceLogin', 'SPANELY'),
    ('https://accounts.google.com/v3/signin/identifier?dsh=S319449056%3A1681711664643096&continue=https%3A%2F%2Fwww.google.com%2Fmaps%2Fd%2Fviewer%3Fhl%3Dzh-TW%26mid%3D17-3hm4jUFmZ9yAwU5273uhkMzBhcVRQ%26ll%3D24.04740285808056%2C120.10402299999998%26z%3D7&ec=GAZA2gE&followup=https%3A%2F%2Fwww.google.com%2Fmaps%2Fd%2Fviewer%3Fhl%3Dzh-TW%26mid%3D17-3hm4jUFmZ9yAwU5273uhkMzBhcVRQ%26ll%3D24.04740285808056%2C120.10402299999998%26z%3D7&hl=zh-TW&ifkv=AQMjQ7QvTP5wsn10jaX4xiO_Krwor5vdZe7YIBwx9GaIbXcLHt2UkoJv5hMyYYI1paOJSAWpcoeMyA&passive=1209600&flowName=GlifWebSignIn&flowEntry=ServiceLogin', 'WHITE5082'),
]
