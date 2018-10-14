celery -A tasks worker --loglevel=INFO -P solo -Q celery --without-gossip --without-mingle
