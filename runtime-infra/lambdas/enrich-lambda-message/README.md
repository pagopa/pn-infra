# Istruzione per costruire il package zip caricare su bucket

```shell
rm -f enrich-lambda-message.zip
pip install --target ./package requests
cd package
zip -r ../enrich-lambda-message.zip .
cd ..
zip -g enrich-lambda-message.zip enrich-lambda-message.py
```

