#!/bin/bash
cd /opt/Crawlab
source venv/bin/activate
python run_crawler.py "$@"
