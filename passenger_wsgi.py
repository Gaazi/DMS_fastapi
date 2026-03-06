# یہ فائل صرف cPanel کے Passenger کو خاموش رکھنے کے لیے ہے۔
# اصل ٹریفک .htaccess کے RewriteRule کے ذریعے
# Uvicorn (port 8001) کو جاتی ہے۔
def application(environ, start_response):
    start_response('200 OK', [('Content-Type', 'text/plain')])
    return [b"Uvicorn is handling requests on port 8001"]
